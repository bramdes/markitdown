# File to Markdown Converter Web App

## Overview
A Flask web application that converts documents (PDF, DOCX, PPTX) to Markdown format with parallel processing support. Features a modern web UI for batch file conversion with real-time status updates.

## Features
- **Parallel Processing**: Converts multiple files simultaneously using multi-threading (up to CPU cores - 1)
- **Batch Operations**: Process multiple files at once with glob pattern support
- **Real-time Status**: Live updates showing conversion progress for each file
- **Modern UI**: Clean, responsive interface with gradient design
- **File Pattern Support**: Use wildcards (`*.pdf`) and recursive patterns (`**/*.docx`)

## Requirements
```bash
# Required Python packages
flask
markitdown
```

## Installation
```bash
# Install dependencies
python -m pip install flask markitdown

# Run the application
python converter_app.py
```

## Usage

### Web Interface
1. Open http://localhost:5555 in your browser
2. Enter file paths in the text area (one per line)
3. Click "Start Conversion" or press Ctrl+Enter
4. Monitor real-time conversion status

### Supported Input Formats
- Single file: `C:\Users\Documents\file.pdf`
- All files in folder: `C:\Users\Documents\*.pdf`
- Recursive search: `C:\Users\Documents\**\*.pdf`
- Multiple extensions: List multiple paths, one per line

### Supported File Types
- PDF files (`.pdf`)
- Word documents (`.docx`)
- PowerPoint presentations (`.pptx`)
- Text files (`.txt`)
- Markdown files (`.md`)

## Architecture

### Components
1. **converter_app.py**: Main Flask application with web UI
2. **convert_to_markdown.py**: Core conversion logic using markitdown
3. **ThreadPoolExecutor**: Manages parallel file processing
4. **Status Tracking**: Thread-safe dictionary with real-time updates

### Parallel Processing
- Uses ThreadPoolExecutor with `CPU_COUNT - 1` workers
- Each file processed in separate thread
- Thread-safe status updates with locking
- Non-blocking background processing

### Conversion Flow
1. User submits file paths via web UI
2. Paths expanded using glob patterns
3. Files queued with "Queued" status
4. ThreadPoolExecutor processes files in parallel
5. Each file status updated: Queued → Processing → Completed/Error
6. Real-time updates sent to browser every 2 seconds

## API Endpoints

### GET `/`
Returns the main HTML interface

### POST `/convert`
Submits files for conversion
```json
Request:
{
    "paths": ["C:\\path\\to\\file.pdf", "C:\\path\\*.docx"]
}

Response:
{
    "success": true,
    "queued": 5,
    "files": ["file1.pdf", "file2.pdf", ...]
}
```

### GET `/status`
Returns current conversion status for all files
```json
Response:
{
    "C:\\path\\file.pdf": {
        "status": "Completed",
        "message": "Successfully converted to: C:\\path\\file.md",
        "timestamp": "2025-01-03T10:30:00"
    }
}
```

### POST `/clear`
Clears conversion history

## Status States
- **Queued**: File waiting to be processed
- **Processing**: Currently converting
- **Completed**: Successfully converted
- **Error**: Conversion failed (with error message)

## Configuration

### Port
Default: 5555
Change in: `app.run(debug=False, port=5555, host='0.0.0.0')`

### Workers
Default: `CPU_COUNT - 1`
Modify: `MAX_WORKERS` variable

### Timeout
Default: 120 seconds per file
Modify in: `convert_to_markdown.py`, line 50

## File Output
Converted files are saved with `.md` extension in the same directory as the source file.

### Output Format
```markdown
# File: example.pdf
# Path: C:\Users\Documents\example.pdf

[Converted markdown content...]
```

## Performance
- Parallel processing scales with CPU cores
- Typical conversion speed: 2-5 seconds per file
- Memory efficient with streaming processing
- Handles large batches (tested with 100+ files)

## Error Handling
- File not found: Graceful error with message
- Conversion timeout: 120-second limit per file
- Invalid formats: Error message with details
- Thread-safe error reporting

## Security Considerations
- Runs on all network interfaces (`0.0.0.0`)
- No authentication (localhost use recommended)
- File system access based on user permissions
- Consider firewall rules for production use

## Troubleshooting

### Common Issues
1. **Port already in use**: Change port in `app.run()`
2. **Import errors**: Install required packages
3. **Permission denied**: Check file/folder permissions
4. **Timeout errors**: Increase timeout in conversion script

### Debug Mode
Enable debug mode for detailed error messages:
```python
app.run(debug=True, port=5555, host='0.0.0.0')
```

## Development Notes
- Flask development server (not for production)
- Consider WSGI server (gunicorn, waitress) for production
- Add authentication for network deployment
- Implement rate limiting for public use

## License
Internal use only - uses markitdown library for document conversion