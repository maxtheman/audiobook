from fastapi.responses import FileResponse, JSONResponse
import modal
import os

image = (
    modal.Image
    .debian_slim()
    .apt_install("ffmpeg")
    .pip_install(["pymupdf",
                   "TTS",
                   "torch",
                   "litellm",
                   "pydub",
                   "tqdm"])
)

mounts = [modal.Mount.from_local_dir("/Users/max/Documents/rethink-stats/audiobook/mount", remote_path="/mount")]
volume = modal.NetworkFileSystem.persisted("job-storage-vol")

stub = modal.Stub(name="audiobook-server")


endpoint = modal.web_endpoint

@stub.function(network_file_systems={"/outputs": volume}, image=image, mounts=mounts)
@endpoint(label="download-waves")
async def download_combined_wavs(dir_name: str):
    remote_file = f"/outputs/pages/{dir_name}/audio/combined.wav"
    if os.path.isfile(remote_file) and os.path.getsize(remote_file) > 500:
        return FileResponse(remote_file)
    else:
        return False
    
@stub.function(network_file_systems={"/outputs": volume}, image=image, mounts=mounts)
@endpoint(label="delete-waves")
async def delete_combined_wavs(dir_name: str):
    print(dir_name)
    print(os.listdir("/outputs/pages/"))
    remote_directory = f"/outputs/pages/{dir_name}/"
    print(os.listdir(remote_directory))
    wav_file = remote_directory + "combined.wav"
    if os.path.exists(wav_file):
        os.remove(wav_file)  # delete the original file
        return True
    else:
        return False
    
@stub.function(network_file_systems={"/outputs": volume}, image=image, mounts=mounts)
@endpoint(label="list-waves")
async def list_all_wavs():
    directories = os.listdir("/outputs/pages/")
    print(directories)
    wav_directories = [dir for dir in directories if os.path.isfile(f"/outputs/pages/{dir}/audio/combined.wav")]
    #return file size also {dir: directors, size: size}
    wav_directories = [{"dir": dir, "size": os.path.getsize(f"/outputs/pages/{dir}/audio/combined.wav")} for dir in wav_directories]
    if len(wav_directories) == 0:
        return False
    print('filled: ', wav_directories)
    return JSONResponse(content=wav_directories)
