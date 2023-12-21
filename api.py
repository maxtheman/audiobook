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
    # files_to_download = get_list()
    # for file in files_to_download:
    #     name = file['dir']
    #     size = file['size']
    #     download(name, size)
    #     # delete(index)
    # list()
    concatenate_audio_pydub("final_combined_wavs/", "chapter_2.wav")