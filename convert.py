import asyncio
import fitz
import modal
from audiobook import setup_tts, make_page_reading, Chapter, Doc, PydanticPage, Figures, load_chapters_from_yaml

# Initialize the modal stub and configure the container image
stub = modal.Stub(name="audiobook")
# For tracking the working document
stub.working_doc_dict = modal.Dict.new()
image = (
    modal.Image
    .debian_slim()
    .apt_install("ffmpeg")
    .pip_install(["pymupdf", "TTS", "torch", "litellm", "pydub", "tqdm", "pydantic==2.5.2"])
)
mounts = [modal.Mount.from_local_dir("/Users/max/Documents/rethink-stats/audiobook/mount",
                                      remote_path="/mount")]
volume = modal.NetworkFileSystem.persisted("job-storage-vol")

# Function to download the TTS model to the container
@stub.function(network_file_systems={"/outputs": volume}, image=image, mounts=mounts)
def download_tts_model():
    setup_tts()
    return True

# Asynchronous function to process each page and generate audio
@stub.function(gpu="any", network_file_systems={"/outputs": volume}, 
               image=image, 
               mounts=mounts, 
               secret=modal.Secret.from_name("OPENAI_API_KEY"), 
               timeout=1800)
async def make_doc_readings(doc_path_local, page_number):
    '''Get the current working document from the working_doc_dict, process the indicated page,
    and update the working_doc_dict with the new pages and figures'''
    # Initialize TTS and open the document
    tts = setup_tts()
    doc = fitz.open("/" + doc_path_local)
    page = doc[page_number]
    existing_figure_names = []

    figures = await stub.working_doc_dict.get.aio("figures")
    chapters = await stub.working_doc_dict.get.aio("chapters")

    if figures is None:
        figures = []
    else:
        get_figure_names = lambda figure: figure.figure_name
        existing_figure_names = list(map(get_figure_names, figures))
    
    if chapters is None:
        chapters = []

    current_chapter = None
    for chapter in chapters:
        if chapter.chapter_start_page <= page_number <= chapter.chapter_end_page:
            current_chapter = chapter
            break
    
    header_and_footer = {'header': None, 'footer': None}
    if current_chapter.chapter_title_header != "":
        header_and_footer['header'] = current_chapter.chapter_title_header
    if current_chapter.chapter_title_footer != "":
        header_and_footer['footer'] = current_chapter.chapter_title_footer

    # Process the page and generate audio
    page = make_page_reading(existing_figure_names, tts, page, page_number, header_and_footer, speaker_location="/mount/speaker-longer-enhanced-90p.wav")

    #check that page is a PydanticPage
    assert isinstance(page, PydanticPage)

    # add page.figures to figures
    figures.extend(page.figures)
    await stub.working_doc_dict.put.aio("figures", figures)


# Main entry point for local execution
async def main_thread():
    doc_path_local = "mount/book.pdf"

    # Download TTS model asynchronously
    await download_tts_model.remote.aio()
    print("TTS model downloaded")

    # Load chapters and initialize working_doc as a distributed dict
    chapters = load_chapters_from_yaml('chapters.yaml')
    # check that chapters are valid Chapter objects
    for chapter in chapters:
        assert isinstance(chapter, Chapter)
    await stub.working_doc_dict.put.aio("chapters", chapters)
    await stub.working_doc_dict.put.aio("figures", [])

    for chapter in chapters:
        page_start = chapter.chapter_start_page
        page_end = chapter.chapter_end_page
        # Process each page asynchronously
        tasks = [make_doc_readings.remote.aio(doc_path_local, page_number)
                for page_number in range(page_start, page_end + 1)]

    await asyncio.gather(*tasks)

@stub.local_entrypoint()
def main():
    asyncio.run(main_thread())
