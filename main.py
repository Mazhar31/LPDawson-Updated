import os
import base64
import openai
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from google_sheets import write_rows_to_sheet
from google_drive import upload_file_to_drive
import ast
import re
import uvicorn

load_dotenv()
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_JSON_KEY_PATH = os.getenv("GOOGLE_KEY_PATH")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DRIVE_FOLDER_ID_WEST = os.getenv("DRIVE_FOLDER_ID")
WORKSHEET_NAME = os.getenv("SHEET_NAME")

openai.api_key = OPENAI_API_KEY

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PROMPTS

WEIGH_SCALE_PROMPT = """
You are a precise data extractor.

Extract and structure the data from the provided weigh scale load slip image using this exact format:

[
  ["Company", "Louisiana Pacific #473"],
  ["Location", "Dawson Creek #473"],
  ["Scale Site", "473"],
  ["Stratum", "31"],
  ["PopStrYear", "48093126"],
  ["Truck", "1367 4EG"],
  ["Trailer", "8C"],
  ["Contractor", "200495 4EVERGREEN RESOURCES LTD"],
  ["T.Mark", "HK6005"],
  ["Cut Blk", "LM066"],
  ["Patch", ""],
  ["Frm/Cond/Pr", "PULP-LOGS"],
  ["In LDS#", "257042"],
  ["Species", ""],
  ["Date In", "08/Sep/25"],
  ["In Time", "17:05"],
  ["Out Time", "17:31"],
  ["Scaler1/2/S", "461H/461H/"],
  ["Yard Time", "26min"],
  ["Yard", ""],
  ["Source ID", "HK6005-LM066"],
  ["Gross", "64,490 kg"],
  ["Tare", "21,700 kg"],
  ["Net", "42,790 kg"],
  ["Driver", ""],
  ["Form A", "AP LONG 5410-473 - 100%"],
  ["Form B", "AP LONG 5410-473 - 0%"],
  ["Form C", "AP LONG 5410-473 - 0%"],
  ["Weigh Scale Load Slip #", "194647 / 1"],
  ["Load Arrival#", "194"]
]

**Rules:**
- Return values as-is from the image — no reformatting or conversions.
- If any value is missing, leave it blank: `["Field", ""]`
- Return **only** the list structure above — no extra text.
"""

# Shared OCR + GPT function
def extract_and_format_with_gpt4_vision(file_bytes: bytes, file_extension: str, prompt: str) -> list:
    mime_type = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png'
    }.get(file_extension.lower())

    if not mime_type:
        raise ValueError(f"Unsupported image type: {file_extension}")

    base64_image = base64.b64encode(file_bytes).decode("utf-8")

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
        max_tokens=2000,
    )

    reply = response.choices[0].message.content.strip()
    print("GPT Output:\n", reply)

    try:
        match = re.search(r"\[\s*\[.*?\]\s*\]", reply, re.DOTALL)
        if not match:
            raise ValueError("No list found in GPT output.")

        list_str = match.group(0)
        parsed = ast.literal_eval(list_str)

        if isinstance(parsed, list):
            return parsed
        else:
            raise ValueError("Parsed result is not a list.")
    except Exception as e:
        raise ValueError(f"Failed to parse GPT response: {str(e)}")


@app.post("/lpdawson")
async def lpdawson(file: UploadFile = File(...)):
    _, file_extension = os.path.splitext(file.filename)

    try:
        contents = await file.read()

        extracted_data = extract_and_format_with_gpt4_vision(contents, file_extension, WEIGH_SCALE_PROMPT)

        write_rows_to_sheet(SHEET_ID, WORKSHEET_NAME, extracted_data, GOOGLE_JSON_KEY_PATH)

        load_slip_num = ""
        date_str = ""

        for field, value in extracted_data:
            if "weigh scale load slip" in field.lower():
                load_slip_num = value.strip().replace(" / ", "_")
            elif field.upper() == "DATE IN":
                date_str = value.strip().replace("/", "-")

        new_filename = f"{load_slip_num}_{date_str}{file_extension}" if load_slip_num else f"weigh_scale_{date_str}{file_extension}"

        mime_type = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png'
        }.get(file_extension.lower(), 'application/octet-stream')

        file_id, file_link = upload_file_to_drive(
            file_bytes=contents,
            filename=new_filename,
            mimetype=mime_type,
            json_key_path=GOOGLE_JSON_KEY_PATH,
            parent_folder_id=DRIVE_FOLDER_ID_WEST
        )

        return {
            "message": "Success",
            "extracted_data": extracted_data,
            "drive_file_link": file_link
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
