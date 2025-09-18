#!/usr/bin/env python
"""
Convert various document formats to Markdown using markitdown.
Replaces the PowerShell script with pure Python implementation.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# Import MarkItDown - handle both direct execution and module import
try:
    # Try relative import first (when imported as module)
    from .. import MarkItDown
except ImportError:
    # If relative import fails, try absolute import (when run directly)
    import sys
    from pathlib import Path
    
    # Add the parent package to the Python path
    webapp_dir = Path(__file__).parent
    markitdown_package_dir = webapp_dir.parent
    src_dir = markitdown_package_dir.parent
    sys.path.insert(0, str(src_dir))
    
    from markitdown import MarkItDown

def clean_markdown_content(content: str) -> str:
    """
    Remove or replace frequent unwanted strings from markdown content.
    
    Args:
        content: The markdown content to clean
        
    Returns:
        Cleaned markdown content
    """
    import re
    
    # Handle None or empty content
    if not content:
        return ""
    
    # Ensure content is a string
    if not isinstance(content, str):
        content = str(content)
    
    # Map of strings to find and their replacements (case-insensitive)
    # Key: string/pattern to find, Value: replacement string
    string_replacements = {
        "RESTRICTED, NON-SENSITIVE": "",
        "RESTRICTED NON-SENSITIVE": "",
        "RESTRICTED,NON-SENSITIVE": "",
        "RESTRICTED - NON-SENSITIVE": "",
        "RESTRICTED-NON-SENSITIVE": "",
        "Page \\d+ of \\d+": "",  # Regex pattern for page numbers
        "Copyright.*\\d{4}": "",  # Copyright notices
        "# File:": "File:",
        "# Path:": "Path:",
    }
    
    cleaned_content = content
    
    # Apply each replacement
    for find_pattern, replace_with in string_replacements.items():
        # Check if it's a regex pattern (contains common regex characters)
        if any(char in find_pattern for char in ['\\', '[', ']', '(', ')', '*', '+', '?', '.', '^', '$']):
            # Use regex substitution
            cleaned_content = re.sub(find_pattern, replace_with, cleaned_content, flags=re.IGNORECASE)
        else:
            # Simple case-insensitive replacement
            # Escape the pattern for regex and replace all variations
            cleaned_content = re.sub(re.escape(find_pattern), replace_with, cleaned_content, flags=re.IGNORECASE)
    
    # Clean up multiple blank lines (more than 2 consecutive)
    cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
    
    # Clean up multiple spaces
    cleaned_content = re.sub(r'[ \t]+', ' ', cleaned_content)
    
    # Clean up spaces at the beginning of lines (but preserve intentional indentation)
    cleaned_content = re.sub(r'^[ \t]+$', '', cleaned_content, flags=re.MULTILINE)
    
    return cleaned_content.strip()

def convert_file_to_markdown(input_file: str, output_file: Optional[str] = None) -> Tuple[bool, str]:
    """
    Convert a file to Markdown format using markitdown.
    
    Args:
        input_file: Path to the input file
        output_file: Optional path for output file. If not provided, uses input name with .md extension
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    
    # Validate input file exists
    input_path = Path(input_file)
    if not input_path.exists():
        return False, f"File does not exist: {input_file}"
    
    # Resolve full path
    resolved_input = input_path.resolve()
    
    # Determine output file path
    if output_file:
        output_path = Path(output_file)
    else:
        output_path = resolved_input.with_suffix('.md')
    
    # Create a temporary file to avoid file locks
    temp_fd, temp_file = tempfile.mkstemp(suffix=resolved_input.suffix)
    os.close(temp_fd)

    try:
        # Try to copy the source file to temp location with retry logic
        max_retries = 3
        retry_delay = 0.5
        for attempt in range(max_retries):
            try:
                shutil.copy2(resolved_input, temp_file)
                break
            except (IOError, OSError) as e:
                if "being used by another process" in str(e) or "Permission denied" in str(e):
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        # If all retries failed, try reading and writing manually
                        try:
                            with open(resolved_input, 'rb') as src:
                                content = src.read()
                            with open(temp_file, 'wb') as dst:
                                dst.write(content)
                        except Exception as read_error:
                            return False, f"File is in use and cannot be accessed: {str(read_error)}"
                else:
                    raise
        
        # Build the header for the markdown file
        header = f"# File: {resolved_input.name}\n# Path: {resolved_input}\n\n"
        
        # Use MarkItDown directly instead of subprocess
        try:
            markitdown = MarkItDown()
            result = markitdown.convert(temp_file)
            output_content = result.markdown if result.markdown else ""
        except Exception as e:
            error_msg = f"markitdown conversion failed: {str(e)}"
            return False, error_msg
        
        # Combine header and content, then clean everything
        full_content = header + output_content
        cleaned_content = clean_markdown_content(full_content)
        
        # Write cleaned markdown content to output file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
        
        return True, f"Successfully converted to: {output_path}"
        
    except Exception as e:
        return False, f"Error during conversion: {str(e)}"
    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

def batch_convert(file_paths: list, max_workers: Optional[int] = None) -> dict:
    """
    Convert multiple files to Markdown in parallel using multiprocessing.
    
    Args:
        file_paths: List of file paths to convert
        max_workers: Maximum number of parallel workers (defaults to CPU count)
        
    Returns:
        Dictionary with file paths as keys and (success, message) tuples as values
    """
    if max_workers is None:
        max_workers = min(multiprocessing.cpu_count(), len(file_paths))
    
    results = {}
    
    # Use ProcessPoolExecutor for true parallel processing
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all conversion tasks
        future_to_file = {
            executor.submit(convert_file_to_markdown, file_path): file_path 
            for file_path in file_paths
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                success, message = future.result()
                results[file_path] = (success, message)
            except Exception as e:
                results[file_path] = (False, f"Conversion failed: {str(e)}")
    
    return results

if __name__ == "__main__":
    # Command line usage
    if len(sys.argv) < 2:
        print("Usage: python convert_to_markdown.py <input_file> [output_file]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    success, message = convert_file_to_markdown(input_file, output_file)
    print(message)
    
    if not success:
        sys.exit(1)