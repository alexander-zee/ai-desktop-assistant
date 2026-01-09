# ai-desktop-assistant
ODOO AI

ODOO AI is a lightweight, on-screen desktop assistant built in Python that provides real-time, context-aware insights based on the user’s active screen and input.

It is designed as a practical productivity and accounting assistant, with a particular focus on Odoo workflows, invoice handling, and structured desktop environments such as code editors and ERP systems.

The assistant continuously observes the active screen, interprets visible UI elements, and responds with concise, actionable feedback—without interrupting the user’s workflow.

🔧 Technologies

Python

Tkinter (desktop overlay UI)

OpenAI Responses API (multimodal: text + vision)

PIL (Pillow)

MSS (screen capture)

threading

Windows APIs (win32gui / win32api)

🧠 Core Capabilities

Here’s what ODOO AI can do:

Screen-Aware Observation

Periodically captures a focused region of the screen and produces short, concrete observations based strictly on visible UI elements (e.g. invoices, tables, code files, Odoo views).

Contextual Chat Interaction

Users can ask questions directly in the overlay. Responses are generated using both:

the user’s question

the current screen content

This allows highly contextual replies such as explaining what an invoice field represents, what a visible error means, or what step is missing in an on-screen workflow.

Non-Intrusive Desktop Overlay

Runs as a transparent, always-on-top overlay:

draggable

fade-out when idle

quick focus on interaction

Designed to stay out of the way while remaining instantly accessible.

Multimodal Reasoning

Combines text prompts with compressed screenshots using the OpenAI Responses API, enabling vision-based reasoning instead of relying on window titles or metadata alone.

🧠 The Process

The project started from a simple idea:
What if an assistant could “see” exactly what you’re looking at and respond accordingly—without switching apps?

First, I implemented a screen capture pipeline using MSS, extracting a central region of the active monitor for efficiency. Screenshots are resized and compressed to reduce latency while preserving relevant UI detail.

Next, I built a robust multimodal prompt pipeline using the OpenAI Responses API. Instead of relying on legacy chat completion parsing, responses are read directly from response.output_text, ensuring reliable handling of modern model outputs.

To keep interaction fluid, all model calls run in background threads, preventing UI blocking. The overlay itself is implemented in Tkinter with custom drawing, rounded gradients, fade animations, and minimal visual noise.

Finally, I layered in idle detection and user-triggered interaction, allowing ODOO AI to proactively observe the screen or react directly to user questions.

📐 Methodology

Screen understanding is handled through vision-conditioned language modeling, where the model receives both:

a structured textual prompt

a base64-encoded screenshot

Responses are constrained to:

reference only visible UI elements

avoid generic productivity advice

remain concise (1–3 sentences)

This ensures outputs remain grounded in the user’s actual context rather than speculative or generic suggestions.

📈 What I Learned

Through this project, I deepened my understanding of:

Multimodal AI pipelines (vision + text)

Practical usage of the OpenAI Responses API

Robust model output handling across SDK versions

Designing non-blocking, responsive desktop UIs

Translating AI capabilities into genuinely useful tooling

I also gained experience debugging real-world model integration issues, including payload formatting, response parsing, and model fallback strategies.

🔄 Possible Improvements

Planned or potential extensions include:

OCR-assisted text extraction for structured documents

Deeper Odoo-specific heuristics (invoice validation, reconciliation hints)

Configurable screen regions and observation frequency

Conversation memory across interactions

Multi-monitor support

Optional logging / audit mode for accounting workflows

▶️ Running the Project

To run ODOO AI locally:

pip install -r requirements.txt
python ODOO_AI.py


The assistant launches as a floating overlay on your desktop.

Ensure your OpenAI API key is set:

setx OPENAI_API_KEY "your-api-key"

📌 Project Structure
ODOO_AI.py        — Main application and UI logic
README.md         — Project documentation

📬 Contact

If you’re interested in AI-assisted productivity tools, accounting automation, or context-aware desktop assistants, feel free to reach out:

LinkedIn:
https://www.linkedin.com/in/alexanderzee/
