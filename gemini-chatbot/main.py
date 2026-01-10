"""Simple FastAPI backend for the Gemini Chatbot frontend.

This provides a POST /api/chat endpoint that streams text back to the client.
By default it runs a mock responder (useful for local testing). If you set
the GEMINI_API_KEY environment variable and want to call Google/other LLMs,
the code includes a commented section showing where to plug that in.

Run with:
  pip install -r requirements.txt
  uvicorn main:app --reload --port 8000

The frontend expects a streaming response and will read response.body via a
reader. We stream plain UTF-8 text chunks which the frontend app collects.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import asyncio
from typing import AsyncIterator, List, Dict, Any

app = FastAPI()

# Allow Vite dev server (default origin http://localhost:5173) and local testing
app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


class ChatRequest(BaseModel):
	prompt: str
	history: List[Dict[str, Any]] = []


async def mock_stream_response(prompt: str) -> AsyncIterator[bytes]:
	"""A simple streaming generator that yields chunks of text with a short delay.

	This lets the frontend demonstrate incremental updates while the model "thinks".
	"""
	response_text = f"You said: {prompt}\nThis is a mock reply generated locally."
	# Yield character-by-character (or in small groups) with a slight delay
	chunk_size = 12
	for i in range(0, len(response_text), chunk_size):
		chunk = response_text[i : i + chunk_size]
		await asyncio.sleep(0.06)  # small delay to simulate streaming
		yield chunk.encode("utf-8")


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
	"""Handle chat requests and stream back model output.

	If you want to call a real LLM (Google Gemini, OpenAI, etc.), set the
	GEMINI_API_KEY (or other env var) and replace the mock generator with
	a streaming call to the provider. Example (pseudocode) is left below.
	"""
	prompt = req.prompt

	if not prompt or not prompt.strip():
		raise HTTPException(status_code=400, detail="Prompt is required")

	# If you have a real API key and want to call Google Gemini, you could do:
	# import google.generativeai as genai
	# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
	# model = "models/text-bison-001"  # example
	# response = genai.generate_text(model=model, prompt=prompt)
	# and stream response.content or use their streaming API if available.

	# For now, return the mock streamer
	return StreamingResponse(mock_stream_response(prompt), media_type="text/plain; charset=utf-8")


if __name__ == "__main__":
	import uvicorn

	uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
