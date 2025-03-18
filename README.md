# AIEVAL_Backend

## Overview
AIEVAL_Backend is a backend service built using FastAPI. It leverages Supabase for database services and includes several dependencies for various functionalities such as data validation, image processing, and AI services.

## Table of Contents
- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Docker](#docker)
- [Environment Variables](#environment-variables)
- [Contributing](#contributing)
- [License](#license)

## Requirements
- Python 3.11
- Docker (optional, for containerized deployment)

## Installation

### Local Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/mariswarycharan/AIEVAL_Backend.git
   cd AIEVAL_Backend
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   uvicorn main:app --reload
   ```

### Docker Setup
1. Build the Docker image:
   ```bash
   docker build -t aieval_backend .
   ```

2. Run the Docker container:
   ```bash
   docker run -d -p 8000:8000 aieval_backend
   ```

## Usage
Access the FastAPI application in your browser at `http://localhost:8000`.

## Environment Variables
Create a `.env` file in the project root and add any necessary environment variables. Example:
```env
DATABASE_URL=your-supabase-url
SECRET_KEY=your-secret-key
```

## Contributing
Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License
This project is licensed under the MIT License.
