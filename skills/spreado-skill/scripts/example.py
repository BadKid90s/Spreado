import asyncio
from pathlib import Path
from spreado.publisher.douyin_uploader import DouYinUploader


async def upload_video_example():
    """
    Example script demonstrating how to use the Spreado Python API
    to upload a video to Douyin.
    """
    # 1. Path to your saved cookies (usually generated via 'spreado login douyin')
    cookie_path = Path("cookies/douyin_uploader/account.json")

    if not cookie_path.exists():
        print(f"Error: Cookie file not found at {cookie_path}")
        print("Please run 'spreado login douyin' first.")
        return

    # 2. Initialize the uploader
    uploader = DouYinUploader(cookie_file_path=cookie_path)

    # 3. Define video metadata
    video_file = Path("example_video.mp4")
    if not video_file.exists():
        print(
            f"Warning: Video file {video_file} not found. Please provide a valid file."
        )
        # We'll stop here in this example
        return

    # 4. Perform the upload flow
    print(f"Starting upload for {video_file}...")
    result = await uploader.upload_video_flow(
        file_path=video_file,
        title="Example Title",
        content="This video was uploaded using Spreado's Python API!",
        tags=["Spreado", "Automation"],
        # thumbnail_path=Path("cover.png"), # Optional
    )

    if result:
        print("✓ Upload successful!")
    else:
        print("✗ Upload failed. Check the logs for details.")


if __name__ == "__main__":
    # Run the async function
    try:
        asyncio.run(upload_video_example())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
