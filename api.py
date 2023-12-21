import requests
import os
from audiobook import concatenate_audio_pydub, load_chapters_from_yaml

def get_list():
    response = requests.get("https://maxtheman--list-waves-dev.modal.run")
    if response.status_code == 200:
        return response.json()
    else:
        print(response.status_code)

def download(name, size):
    response = requests.get(f"https://maxtheman--download-waves-dev.modal.run?dir_name={name}")
    if response.status_code == 200:
        #check file size
        if len(response.content) != size:
            raise Exception("File size does not match")
        local_directory = f"final_combined_wavs/"
        if not os.path.exists(local_directory):
            os.makedirs(local_directory)
        new_dir_name = int(name)
        new_file_name = f"{new_dir_name}.wav"
        new_file_path = os.path.join(local_directory, new_file_name)
        with open(new_file_path, 'wb') as f:
            f.write(response.content)
    else:
        print(response.status_code)

def delete(dir_name):
    response = requests.get(f"https://maxtheman--delete-waves-dev.modal.run?dir_name={dir_name}")
    if response.status_code == 200:
        print("Deleted")
    else:
        print(response.status_code)

if __name__ == "__main__":
    all_files = get_list()
    chapters = load_chapters_from_yaml('chapters.yaml')
    # check if the file dirs are pages in chapters
    files_in_chapters = []
    for file in all_files:
        name = int(file['dir'])
        for chapter in chapters:
            if chapter.chapter_start_page <= name <= chapter.chapter_end_page:
                files_in_chapters.append(file)
                break
    for file in files_in_chapters:
        name = file['dir']
        size = file['size']
        download(name, size)
    for chapter in chapters:
        concatenate_audio_pydub("final_combined_wavs/", f"chapter_{chapter.chapter_number}.wav")
        # move files to subdirectory to clean up
        os.makedirs(f"final_combined_wavs/chapter_{chapter.chapter_number}", exist_ok=True)
        for file in os.listdir("final_combined_wavs/"):
            if file.endswith(".wav"):
                os.rename(f"final_combined_wavs/{file}", f"final_combined_wavs/chapter_{chapter.chapter_number}/{file}")