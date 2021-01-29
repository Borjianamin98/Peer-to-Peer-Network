import os
import shutil
from pathlib import Path


def get_file_chunks_path(file_directory, file_number, chunk_number):
    return "{}/{}/{}".format(file_directory, file_number, chunk_number)


def get_file_path(file_directory, file_number):
    return "{}/{}".format(file_directory, file_number)


def store_split_file(file_path, file_directory, file_number, chunk_size):
    file_name = os.path.basename(file_path)
    Path(get_file_path(file_directory, file_number)).mkdir(parents=True, exist_ok=True)

    chunk_number = 0
    with open(file_path, 'rb') as file:
        chunk = file.read(chunk_size)
        while chunk:
            with open(get_file_chunks_path(file_directory, file_number, chunk_number), 'wb') as chunk_file:
                chunk_file.write(chunk)
            chunk_number += 1
            chunk = file.read(chunk_size)

    new_file_info = {
        "file_name": file_name,
        "file_number": file_number,
        "chunks_count": chunk_number,
        "available_chunks": [True for _ in range(chunk_number)]
    }
    return new_file_info


def join_files(file_name, file_directory, file_number, chunks_count):
    with open(file_name, 'wb') as output_file:
        for chunk in range(chunks_count):
            with open(get_file_chunks_path(file_directory, file_number, chunk), 'rb') as file:
                file_bytes = file.read()
                output_file.write(file_bytes)


def get_chunk_file_bytes(file_directory, file_number, chunk):
    with open(get_file_chunks_path(file_directory, file_number, chunk), 'rb') as file:
        return file.read()


def save_chunk_file_bytes(file_directory, file_number, chunk, chunk_bytes):
    Path(get_file_path(file_directory, file_number)).mkdir(parents=True, exist_ok=True)
    with open(get_file_chunks_path(file_directory, file_number, chunk), 'wb') as file:
        file.write(chunk_bytes)


def remove_local_chunks(file_directory, file_number):
    if os.path.exists(get_file_path(file_directory, file_number)):
        shutil.rmtree(get_file_path(file_directory, file_number))
