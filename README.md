# ShopWise AI — Intelligent E-Commerce Shopping Assistant

ShopWise AI is a multimodal, agentic e-commerce assistant built with Google's **Agent Development Kit (ADK)**, deployed to **Vertex AI Agent Engine**, and powered by Google Cloud's AI platform infrastructure.

It helps users search local and external product inventory, generate AI product images and video showcases, recall past search queries across sessions using persistent memory, convert currency rates live, and locate nearby physical retail stores.

![ShopWise AI Demo](./demo.gif)

---

## ✨ Implemented Features & Tool Capabilities

The agent is powered by `gemini-flash-latest` and equipped with the following verified tools and integrations:

### 📦 Product & Catalog Management
- **Local Firestore Inventory Search (`search_products`)**: Queries Firestore's `products` collection with keyword matching, price filters, and category filters.
- **Product Registration (`add_product`)**: Inserts new items into the Firestore product catalog.
- **External Online Catalog (`fetch_external_catalog_products`)**: Connects to external public e-commerce APIs (FakeStore) to fetch live product listings.

### 🎨 Multimodal Media Generation
- **Imagen 3 Image Generation (`generate_product_image`)**: Generates product photos using `gemini-3.1-flash-lite-image`, automatically saving session artifacts for the Playground panel and uploading public image bytes to Cloud Storage.
- **Omni Video Generation (`generate_product_video`)**: Generates 3-second e-commerce product videos using `gemini-omni-flash-preview` in the `global` region via the Vertex AI Interactions API, saving session artifacts and public GCS video URLs.

### 🧠 Memory & Personalization
- **Vertex AI Memory Bank (`PreloadMemoryTool` & `generate_memories_callback`)**: Automatically extracts and persists user preferences and shopping history into Vertex AI Memory Bank.
- **Firestore Search History (`record_search` & `get_search_history`)**: Stores and retrieves recent user search terms and query timestamps.

### 🗺️ Geolocation & Retail Discovery
- **Address Geocoding (`geocode_address`)**: Converts street addresses or city names into latitude and longitude using Google Maps API.
- **Nearby Store Search (`find_nearby_places`)**: Locates physical retail stores (electronics, clothing, shopping malls) near coordinates or address queries.

### 📊 Utility & Interface Integration
- **Live Exchange Rates (`get_live_exchange_rate`)**: Fetches real-time international currency exchange rates for instant price conversions.
- **Code Execution Sandbox (`BuiltinCodeExecutor`)**: Executes Python code in a safe sandbox for complex price calculations and data processing.
- **A2UI Declarative Interface (`A2uiSchemaManager`)**: Generates structured, responsive UI cards, columns, and image layouts.

---

## 🛠️ Infrastructure & Google Cloud Architecture

- **Runtime Architecture**: Google Agent Development Kit (ADK) on **Vertex AI Agent Engine (Reasoning Engine)**.
- **Database & Storage**: Google Cloud Firestore (`products`, `search_history`) & Public Google Cloud Storage Bucket for media assets.
- **Memory**: Vertex AI Memory Bank.
- **Frontend App**: Lightweight FastAPI proxy + custom Vanilla HTML/CSS responsive chat interface with interactive prompt chips.

---

## 🚀 Local Setup & Deployment Instructions

### Prerequisites
- Python 3.10+
- Google Cloud SDK (`gcloud`) authenticated to your GCP project.
- Active Vertex AI, Firestore, and Cloud Storage resources.

### 1. Install Backend & Agent Dependencies
```bash
cd app
pip install -r requirements.txt
```

### 2. Run the Agent Locally (Playground)
```bash
python -m google.adk.cli run app
```

### 3. Run the Frontend Locally
```bash
cd ../frontend
pip install -r requirements.txt

export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_NUMBER>/locations/<LOCATION>/reasoningEngines/<ENGINE_ID>"
export AGENT_DIRECTORY="app"

python main.py
```
*The local frontend web UI will be accessible on port 8080.*

### 4. Deploy Agent to Vertex AI Agent Engine
```bash
agents-cli deploy --project <YOUR_GCP_PROJECT_ID> --region us-central1
```

---

## 📋 Planned / Future Enhancements

The following features were outlined in the original design brief and are planned for future iterations:
- *Integrated Payment & Checkout Gateway*: Direct payment processing via Stripe/Google Pay (planned).
- *Order Tracking & Logistics*: Real-time shipping notifications and carrier webhooks (planned).
