from TTS.api import TTS
import torch
from litellm import completion
import base64
import os
from pydub import AudioSegment
from tqdm import tqdm
from functools import reduce
import fitz
import shutil
import yaml
import re
from pydantic import BaseModel, validator
from enum import Enum

def setup_tts():
    os.environ["COQUI_TOS_AGREED"] = "1"
    if os.getenv('USER') != 'max': #hack - only use relative on local system
        os.environ["TTS_HOME"] = "/outputs/models/"
    else:
        os.environ["TTS_HOME"] = "outputs/models/"
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "cpu"  # mps doesn't work yet
        # device = "mps"
    else:
        device = "cpu"

    torch.set_default_device(device)
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    tts.to(device)
    return tts

class LLM(Enum):
    LLAVA = "ollama/llava"
    GPT_VISION = "gpt-4-vision-preview"
    GPT_TURBO = "gpt-4-1106-preview"

def get_llm_response(model: LLM, messages, images = None) -> str:
        '''Responsible for making the completions from LiteLLM'''
        messages = messages
        _images = []
        max_tokens=4000
        params = {
                'model': model.value,
                'max_tokens': 4000,
                'messages': messages,
            }
        if images:
            if type(images) == 'list':
                _images = images
            else:
                _images = [images]
        else:
            _images = None
        if type(model) == str:
            model = LLM(model)
        if model == LLM.LLAVA and _images:
            if type(images) == 'list':
                params['images'] = _images
            else:
                params['images'] = [_images]
        response = completion(**params)
        return response.choices[0].message.content

def describe_image(image_uri, figure_name, surrounding_text, model=LLM.GPT_VISION, mode="specific_image"):
    if type(model) == str:
        model = LLM(model)
    if image_uri is None:
        raise ValueError("No image provided")
    if open(image_uri, "rb").read() is None:
        raise ValueError("Image could not be read")
    image = base64.b64encode(open(image_uri, "rb").read()).decode("utf-8")
    if mode == "specific_image":
        message = "Please describe the picture named {0} on this page. How is it related to the following text? Text: {0} Describe its importance to the passage, in detail. Describe the image directly as if you were writing a description in a book, e.g., say 'the image is' instead of 'the image you shared is', for example.".format(figure_name, surrounding_text)
    elif mode == "general_cleanup":
        message = "The following text is from an OCR of a page. Obey the following rules exactly — failure to do so could result in user misunderstanding and harm. You have the original image of the page attached. Your job is to validate the work and clean up the OCR. If the page contains images or figures, ignore their presence. Please provide a cleaned up version of this text that could easily be passed to a text-to-speech program, removing any obvious grammatical errors resulting from the OCR of the page. More formal texts may have chapter names at the start of the page — remove these if they don't make sense inline with the text. The downstream program can only handle english and numbers, so mathematical symbols, tables, and special characters — including brackets — should all be clarified. Remove extraneous characters if they have been added, and for easy listening add additonal language if it's not clear that something is a title, or that it's about to transition to a table or math equation, for example. Do NOT add summaries of the page — this is just one page of the book, the author will summarize if appropriate. If you are unable to clarify, leave it as is. Apart from these instructions, do NOT take liberties with the text. Here is the text {0}".format(surrounding_text)
        response = completion(
            model="gpt-4-1106-preview",
            max_tokens=4000,
            messages=[{ "content": message, "role": "user"}], 
        )
        return response.choices[0].message.content
    if model == LLM.LLAVA:
        messages=[{ "content": message ,"role": "user"}]
        return get_llm_response(model, messages, image)
    if model == LLM.GPT_VISION:
        base64_full_image = f"data:image/jpeg;base64,{image}"
        messages=[{ "content": [message,
                { "type": "image_url", "image_url": { "url": base64_full_image, }}], "role": "user"}]
        return get_llm_response(model, messages)
    else:
        raise ValueError(f"{model} not supported")

# def interpret_figure(figure_name, model=LLM.GPT_VISION):

def chunk_text(text, max_length, page_image, described_figures=None, handle_figures=False):
    if described_figures is None:
        described_figures = set()

    sentences = text.split('.')
    chunks = []
    current_chunk = []

    for sentence in sentences:
        words = sentence.split()
        for word in words:
            # Check if adding the next word exceeds the max length
            if len(' '.join(current_chunk + [word])) > max_length:
                # Add the current chunk to the chunks list
                chunks.append(' '.join(current_chunk))
                # Start a new chunk with the current word
                current_chunk = [word]
            else:
                # Add the word to the current chunk
                current_chunk.append(word)
        
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = []

    described_figures = set()
    return chunks, described_figures

def concatenate_audio_pydub(path, output_file_name, verbose=1):
    '''Concatenate all the audio files in the directory and export the final audio file. Ignores and overwrites the output file name if it's already present in the directory.'''
    # List and sort the audio files in the directory
    audio_file_names = os.listdir(path)
    audio_file_names = [name for name in audio_file_names if name.endswith('.wav') and name != output_file_name]
    audio_file_names.sort(key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))

    audio_clip_paths = [os.path.join(path, name) for name in audio_file_names]

    if verbose:
        audio_clip_paths = tqdm(audio_clip_paths, "Reading audio files")

    # Read the audio files and add them to the clips list
    clips = [AudioSegment.from_file(clip_path, format="wav") for clip_path in audio_clip_paths]

    if not clips:
        raise ValueError("No audio clips provided")

    # Use reduce to concatenate the clips
    final_clip = reduce(lambda x, y: x + y, clips)

    # Export the final concatenated audio
    output_path = os.path.join(path, output_file_name)
    final_clip.export(output_path, format="wav")


class Figures(BaseModel):
    figure_name: str
    page_number: int
    figure_description: str

class PydanticPage(BaseModel):
    page_number: int
    page_text: str
    page_image_uri: str
    page_audio_uri: str
    figures: list[Figures]

class Page():
    def __init__(self, page, page_number, header_and_footer={'header': None, 'footer': None}):
        self.page_audio_uri = "outputs/pages/{0}/audio".format(page_number)
        self.page_image_uri = "outputs/pages/{0}/image".format(page_number)
        if os.getenv('USER') != 'max': #if not local
            self.page_audio_uri = "/outputs/pages/{0}/audio".format(page_number)
            self.page_image_uri = "/outputs/pages/{0}/image".format(page_number)
        if not os.path.exists(self.page_audio_uri):
            os.makedirs(self.page_audio_uri)
        if not os.path.exists(self.page_image_uri):
            os.makedirs(self.page_image_uri)
        full_image_path = self.page_image_uri + "/page.png"
        page_image = page.get_pixmap().save(full_image_path)
        self.page_number = page_number
        self.page_text = page.get_text()
        if header_and_footer['header']:
            header = header_and_footer['header']
            if self.page_text.startswith(header):
                self.page_text = self.page_text[len(header):]
        if header_and_footer['footer']:
            footer = header_and_footer['footer']
            if self.page_text.endswith(footer):
                self.page_text = self.page_text[:-len(footer)]
        self.cleaned_text = describe_image(full_image_path, "", self.page_text, mode="general_cleanup")
        self.figures = []
    
    def set_figures(self, figures):
        self.figures = figures

    def extract_figure_names(self):
        figure_regex = r'Figure (\d+\.\d+)'
        figure_names = re.findall(figure_regex, self.page_text)
        return figure_names
    
    def check_if_image_is_present(self, figure_name):
        prompt = "Looks at this page. Does it contain an image titled {0}? Return only the word True, or the word False.".format(figure_name, self.page_text)
        image = open(self.page_image_uri + "/page.png", "rb").read()
        image_base64 = base64.b64encode(image).decode("utf-8")
        base_64image_encoded = f"data:image/jpeg;base64,{image_base64}"
        messages=[{ "content": [prompt,
                { "type": "image_url", "image_url": { "url": base_64image_encoded, }}], "role": "user"}]
        response = get_llm_response(LLM.GPT_VISION, messages)
        if "True" in response:
            return True
        else:
            return False
        
    def combine_cleaned_text_and_descriptions(self):
        '''Take all Figures and create one string that starts by saying: "Description of images on page"
        and then lists all the figures and their descriptions.
        Then, says "Continuing the main passage:" and appends the cleaned text to the end of the string 
        and return it.'''
        if len(self.figures) == 0:
            return self.cleaned_text
        final_text = "Description of images on page: "
        for figure in self.figures:
            final_text += figure.figure_name + ": " + figure.figure_description + ". "
        final_text += "All images described. Continuing the main passage now: " + self.cleaned_text
        return final_text

    def return_pydantic_page(self):
        return PydanticPage(page_number=self.page_number,
                            page_text=self.combine_cleaned_text_and_descriptions(),
                            page_image_uri=self.page_image_uri + "/page.png",
                            page_audio_uri=self.page_audio_uri + "/combined.wav",
                            figures=self.figures)

    def __str__(self):
        return self.page_text

class Chapter(BaseModel):
    chapter_number: int
    chapter_title_header: str
    chapter_title_footer: str
    chapter_start_page: int
    chapter_end_page: int

class Doc(BaseModel):
    pages: list[PydanticPage]
    figures: list[Figures]
    chapters: list[Chapter]

def make_page_reading(existing_figures, tts, page, page_number, header_and_footer={'header': None, 'footer': None}, speaker_location="speaker-longer-enhanced-90p.wav"):
    '''This function literally makes the out-loud TTS readings of the page and saves the file
    existing_figures: list of figures already described in the document
    tts: tts instance from setup_tts
    page: page from fitz.open
    page_number: page number from fitz.open
    '''
    working_page = Page(page, page_number)
    if header_and_footer['header'] is None and header_and_footer['footer'] is None:
        pass
    else:
        working_page = Page(page, page_number, header_and_footer)
    # This is the core part of the poop below that needs to be refactored
    figures_on_page = working_page.extract_figure_names()
    figures = []
    for figure_name in figures_on_page:
        #check if the figure has already been described in doc
        if figure_name not in existing_figures:
            if working_page.check_if_image_is_present(figure_name):
                description = describe_image(working_page.page_image_uri + "/page.png",
                                            figure_name,
                                            working_page.page_text)
                figure = Figures(figure_name=figure_name,
                                page_number=page_number,
                                figure_description=description)
                figures.append(figure)
                existing_figures.append(figure_name)  # Update the existing_figures list
    working_page.set_figures(figures)
    combined_text = working_page.combine_cleaned_text_and_descriptions()
    final_text_to_write, _ = chunk_text(combined_text, 200, working_page.page_image_uri)
    for page_number, text_chunk in tqdm(enumerate(final_text_to_write)):
        tts.tts_to_file(text=text_chunk,
                        file_path=working_page.page_audio_uri + "/{0}.wav".format(page_number),
                        speaker_wav=speaker_location,
                        language="en")
    concatenate_audio_pydub(working_page.page_audio_uri, "combined.wav")
    return working_page.return_pydantic_page()

def load_chapters_from_yaml(file_path):
    with open(file_path, 'r') as file:
        chapters_data = yaml.safe_load(file)
    return [Chapter(**chapter_data) for chapter_data in chapters_data]
