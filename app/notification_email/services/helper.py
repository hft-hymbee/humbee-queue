from typing import Optional
import unicodedata


def get_mime_type_from_filename(filename: str) -> Optional[str]:
    """
        This function returns the MIME-type of a file. It decides
        MIME-type based on the file-extension. This function isn't strict on
        the case of the filename parameter.

        :type filename: str
        :param filename: case-insensitive filename

        :returns: MIME-type if determined None otherwise
    """

    print(f"inside get_mime_type_from_filename(filename={filename})")

    file_extension = filename.split(".")[-1].lower()

    mime_type = None

    if file_extension == "pdf":
        mime_type = "application/pdf"
    elif file_extension == "png":
        mime_type = "image/png"
    elif file_extension in ("jpeg", "jpg"):
        mime_type = "image/jpeg"
    elif file_extension == "csv":
        mime_type = "text/csv"
    elif file_extension == "heic":
        mime_type = "image/heic"
    elif file_extension == "mp4":
        mime_type = "video/mp4"
    elif file_extension == "mkv":
        mime_type = "video/x-matroska"

    return mime_type


def clean_filename(filename):
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("ascii", "ignore").decode("ascii")
    return filename
