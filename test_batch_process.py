import os
import argparse
from receipt_fetcher import batch_process_files
from utils import send_notification

def main():
    parser = argparse.ArgumentParser(description='Process PDF files in batch')
    parser.add_argument('--data-dir', type=str, help='Directory containing PDF files',
                       default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'))
    parser.add_argument('--files', type=str, nargs='+', help='List of PDF files to process')
    parser.add_argument('--quiet', action='store_true', help='Suppress notifications')

    args = parser.parse_args()

    # Override send_notification if quiet mode is enabled
    if args.quiet:
        def quiet_notification(message, type=None):
            pass
        global send_notification
        send_notification = quiet_notification

    # Get files to process
    if args.files:
        files_to_process = args.files
    else:
        # Process all PDFs in data directory if no files specified
        files_to_process = [f for f in os.listdir(args.data_dir) if f.endswith('.pdf')]

    file_paths = [os.path.join(args.data_dir, filename) for filename in files_to_process]

    # Check if files exist
    missing_files = [f for f in file_paths if not os.path.exists(f)]
    if missing_files:
        print("Files not found:")
        for f in missing_files:
            print(f"- {f}")
        return

    print("Starting batch processing...")
    print(f"Files to process: {', '.join(files_to_process)}")

    try:
        result = batch_process_files(file_paths)

        if result['success']:
            print("\nProcessing results:")
            print(f"- Total files: {result['stats']['total_files']}")
            print(f"- Processed: {result['stats']['processed']}")
            print(f"- Success: {result['stats']['sheet_success']}")
            print(f"- Failed: {result['stats']['sheet_error']}")
        else:
            print(f"\nError: {result['error']}")

    except Exception as e:
        print(f"Error during batch processing: {str(e)}")

if __name__ == "__main__":
    main()
