```bash
modal run convert.py
```

## Directory Structure

The project uses a specific directory structure for input and output files:

- `mount/`: This directory should contain the input PDF file.

- `outputs/`: This directory is created by the scripts and contains the generated audio files and TTS models.
  - `outputs/models/`: Contains the downloaded TTS models.
  - `outputs/pages/`: Contains directories for each page of the PDF, each with its own audio and image files.

Please ensure that the `mount/` directory exists and contains the input PDF file before running the scripts.

## Note

The conversion process can take a significant amount of time, especially for large PDF files. Please be patient and allow the scripts to complete their execution.
```