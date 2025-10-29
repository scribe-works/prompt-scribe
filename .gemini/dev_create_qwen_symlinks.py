import os
import sys
import argparse

def create_symlinks(filenames):
    # Get the project root dynamically
    # Assuming the script is in the project root
    project_root = os.path.abspath(os.path.dirname(__file__))
    gemini_commands_dir = os.path.join(project_root, '.gemini', 'commands')
    qwen_commands_dir = os.path.join(project_root, '.qwen', 'commands')

    os.makedirs(qwen_commands_dir, exist_ok=True)

    for filename_arg in filenames:
        # Handle comma-separated filenames
        for single_filename in filename_arg.split(','):
            single_filename = single_filename.strip()
            if not single_filename:
                continue

            # Ensure .toml extension
            if not single_filename.endswith('.toml'):
                single_filename += '.toml'

            source_path = os.path.join(gemini_commands_dir, single_filename)
            destination_path = os.path.join(qwen_commands_dir, single_filename)

            print(f"Processing: {single_filename}")
            print(f"  Source: {source_path}")
            print(f"  Destination: {destination_path}")

            if not os.path.exists(source_path):
                print(f"Error: Source file not found: {source_path}")
                continue

            if os.path.exists(destination_path):
                if os.path.islink(destination_path):
                    print(f"  Existing symlink found, removing: {destination_path}")
                    os.remove(destination_path)
                else:
                    print(f"  Warning: A file/directory already exists at destination (not a symlink). Skipping to avoid data loss: {destination_path}")
                    continue

            try:
                os.symlink(source_path, destination_path)
                print(f"  Successfully created symlink: {destination_path} -> {source_path}")
            except OSError as e:
                print(f"  Error creating symlink for {single_filename}: {e}")
                print("  On Windows, creating symlinks often requires Administrator privileges or Developer Mode enabled.")

def main():
    parser = argparse.ArgumentParser(description="Create symlinks for .gemini commands in .qwen commands directory.")
    parser.add_argument('filenames', nargs='+', help="One or more command filenames (e.g., 'generate_report', 'update_docs.toml,update_tests')")
    args = parser.parse_args()

    create_symlinks(args.filenames)

if __name__ == '__main__':
    main()
