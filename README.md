# Audiobook Conversion Tool

This tool converts a PDF document into an audiobook. It uses a combination of OCR, image interpretation, and text-to-speech (TTS) technologies to generate an audio file for each page of the document. The tool also provides a server for downloading the generated audio files.

## Installation
Clone this repo and create an environment from requirements.txt

The first time you use modal it will prompt you to log in. You will need to set the OPENAI_API_KEY in modal secrets for this to work.

Running audiobook.py tts requires a model to be downloaded that is ~2GB. It will be saved in the repo itself, but is ignored by fit.

##Usage

Fill out chapters.yaml with the chapters you actively want converted, going off the zero-indexed page numbers.

To start the conversion process, run the following command:

```bash
modal run convert.py
```

To download files run:

```bash
modal run server.py
```

take the urls generated and replace the ones you see in `api.py` (those are mine and won't work for you)

Then run:

```bash
python api.py
```

You may to edit the functionality in `api.py` as appropriate to interact with the api.

## Directory Structure

The project uses a specific directory structure for input and output files:

- `mount/`: This directory should contain the input PDF file.

- `outputs/`: This directory is created by the scripts and contains the generated audio files and TTS models.
  - `outputs/models/`: Contains the downloaded TTS models.
  - `outputs/pages/`: Contains directories for each page of the PDF, each with its own audio and image files.

Please ensure that the `mount/` directory exists and contains the input PDF file before running the scripts.

## Note

The conversion process can take a significant amount of time, especially for large PDF files. The image interpretation is expensive — a full 400 page audiobook could cost $100, $80 in GPT cost from vision and $20 in GPU cost on spot pricing.

This could probably be made cheaper with some optimization, including local llama models (which this has an integration with via Ollama, but is optional.)