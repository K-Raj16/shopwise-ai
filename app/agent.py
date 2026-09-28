# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os
import urllib.parse
import urllib.request
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from .a2ui_utils import a2ui_callback

# IMPORTANT: Hardcoded project ID as required by Agent Platform
PROJECT_ID = "qwiklabs-gcp-03-e5b049a0a94d"
BUCKET_NAME = "shopwise-ai-assets-qwiklabs-gcp-03-e5b049a0a94d"
MEMORY_BANK_ID = "6543738504906539008"

# Initialize Firestore client with hardcoded project ID
db = firestore.Client(project=PROJECT_ID)

# Load Agent Engine resource name from deployment_metadata.json
DEPLOYMENT_META_PATH = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
agent_engine_resource_name = None
if os.path.exists(DEPLOYMENT_META_PATH):
    try:
        with open(DEPLOYMENT_META_PATH, "r") as f:
            meta = json.load(f)
            agent_engine_resource_name = meta.get("remote_agent_runtime_id")
    except Exception:
        pass

# Initialize AgentEngineSandboxCodeExecutor with the Agent Engine resource name
code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name,
    optimize_data_file=True,
)


def memory_service_builder():
    """Memory Bank service builder for future container redeployments."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location="us-central1",
        agent_engine_id=MEMORY_BANK_ID,
    )


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: After each turn, send session events to Memory Bank for durable fact and search extraction."""
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None


def record_search(query: str, category: str = "") -> str:
    """Records a user's search query into the Firestore search_history collection.

    Args:
        query: The search term or keywords entered by the user.
        category: Optional category related to the search.

    Returns:
        A confirmation message.
    """
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    doc_ref = db.collection("search_history").document()

    record = {
        "query": query,
        "category": category,
        "timestamp": now_str,
    }

    doc_ref.set(record)
    return f"Recorded search history: '{query}' in Firestore."


def search_products(query: str = "", category: str = "", max_price: float = 0.0) -> str:
    """Searches products in the local Firestore inventory database and automatically records search history.

    Args:
        query: Optional search keyword to match product name, description, or tags.
        category: Optional category filter (e.g. 'Electronics', 'Furniture', 'Kitchen', 'Apparel').
        max_price: Optional maximum price filter (0.0 means no limit).

    Returns:
        A list of matching products formatted as string records.
    """
    if query or category:
        try:
            record_search(query=query if query else category, category=category)
        except Exception:
            pass

    products_ref = db.collection("products")
    docs = products_ref.stream()

    results = []
    q_lower = query.lower() if query else ""
    cat_lower = category.lower() if category else ""

    for doc in docs:
        p = doc.to_dict()
        # Category filter
        if cat_lower and cat_lower not in p.get("category", "").lower():
            continue
        # Price filter
        if max_price > 0 and p.get("price", 0.0) > max_price:
            continue
        # Keyword query filter
        if q_lower:
            text_corpus = f"{p.get('name', '')} {p.get('description', '')} {' '.join(p.get('tags', []))}".lower()
            if q_lower not in text_corpus:
                continue

        results.append(p)

    if not results:
        return "No products found matching the criteria in local inventory."

    formatted = []
    for p in results:
        status = "In Stock" if p.get("in_stock", True) else "Out of Stock"
        formatted.append(
            f"[{p.get('id')}] {p.get('name')} | Category: {p.get('category')} | Price: ${p.get('price', 0.0):.2f} | "
            f"Rating: {p.get('rating')} | Status: {status}\n  Description: {p.get('description')}"
        )

    return "\n\n".join(formatted)


def add_product(name: str, category: str, price: float, description: str, tags: str = "") -> str:
    """Adds a new product item into the Firestore product catalog.

    Args:
        name: The name of the product.
        category: Category of the product (e.g., Electronics, Home, Apparel).
        price: Price of the product in USD.
        description: Detailed product description.
        tags: Comma-separated tags (e.g., 'wireless,audio,headphones').

    Returns:
        A confirmation message with the generated product ID.
    """
    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    doc_ref = db.collection("products").document()
    product_id = f"prod_{doc_ref.id[:6]}"

    product_data = {
        "id": product_id,
        "name": name,
        "category": category,
        "price": float(price),
        "description": description,
        "rating": 5.0,
        "in_stock": True,
        "tags": tag_list,
    }

    doc_ref.set(product_data)
    return f"Successfully added product '{name}' with ID '{product_id}' to Firestore!"


def get_search_history(limit: int = 5) -> str:
    """Retrieves recent search query history for the user from Firestore.

    Args:
        limit: Maximum number of recent search records to retrieve (default 5).

    Returns:
        A list of recent search terms and timestamps.
    """
    history_ref = db.collection("search_history")
    docs = history_ref.stream()

    history_records = [doc.to_dict() for doc in docs]
    if not history_records:
        return "No search history records found."

    # Sort records by timestamp descending if present
    history_records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    recent = history_records[:limit]

    formatted = []
    for h in recent:
        cat_info = f" ({h.get('category')})" if h.get("category") else ""
        formatted.append(f"- Query: '{h.get('query')}'{cat_info} | Date: {h.get('timestamp')}")

    return "Recent User Search History:\n" + "\n".join(formatted)


def get_live_exchange_rate(from_currency: str = "USD", to_currency: str = "EUR") -> str:
    """Fetches real-time live currency exchange rates to convert product prices.

    Args:
        from_currency: Base currency code (e.g. 'USD', 'EUR', 'GBP'). Default is 'USD'.
        to_currency: Target currency code (e.g. 'EUR', 'GBP', 'JPY', 'CAD', 'AUD'). Default is 'EUR'.

    Returns:
        A string with the current exchange rate and update date.
    """
    from_curr = from_currency.upper().strip()
    to_curr = to_currency.upper().strip()
    url = f"https://open.er-api.com/v6/latest/{from_curr}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ShopWise-AI/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                rates = data.get("rates", {})
                if to_curr in rates:
                    rate = rates[to_curr]
                    update_date = data.get("time_last_update_utc", "latest")
                    return f"1 {from_curr} = {rate:.4f} {to_curr} (as of {update_date})."
                return f"Target currency '{to_curr}' not found in exchange rate table."
            return f"Failed to fetch exchange rates (HTTP status {response.status})."
    except Exception as e:
        return f"Error fetching live exchange rate: {str(e)}"


def fetch_external_catalog_products(category: str = "", query: str = "") -> str:
    """Fetches real e-commerce products from the public FakeStore API catalog.

    Args:
        category: Optional category ('electronics', 'jewelery', "men's clothing", "women's clothing").
        query: Optional search keyword to filter product title or description.

    Returns:
        A formatted list of products retrieved from the public online store API.
    """
    cat_clean = category.lower().strip()
    if cat_clean in ["electronics", "jewelery", "men's clothing", "women's clothing"]:
        url = f"https://fakestoreapi.com/products/category/{cat_clean}"
    else:
        url = "https://fakestoreapi.com/products"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ShopWise-AI/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))

                if query:
                    q_lower = query.lower().strip()
                    data = [
                        p
                        for p in data
                        if q_lower in p.get("title", "").lower()
                        or q_lower in p.get("description", "").lower()
                    ]

                if not data:
                    return f"No external products found matching category='{category}' and query='{query}'."

                formatted = []
                for item in data[:5]:
                    rating = item.get("rating", {}).get("rate", "N/A")
                    formatted.append(
                        f"• {item.get('title')} (${item.get('price')})\n"
                        f"  Category: {item.get('category')} | Rating: {rating}/5.0\n"
                        f"  Description: {item.get('description')[:120]}..."
                    )

                return "External Public Catalog Results (via FakeStore API):\n\n" + "\n\n".join(formatted)
            return f"Failed to fetch external catalog (HTTP status {response.status})."
    except Exception as e:
        return f"Error fetching external product catalog: {str(e)}"


def geocode_address(address: str) -> str:
    """Converts a street address or location name into geographic latitude and longitude coordinates.

    Args:
        address: The full address or location name to geocode (e.g. '1600 Amphitheatre Parkway, Mountain View, CA').

    Returns:
        A string record with formatted address, latitude, and longitude.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    encoded_address = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ShopWise-AI/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") == "OK" and data.get("results"):
                first_result = data["results"][0]
                formatted_addr = first_result.get("formatted_address", address)
                location = first_result.get("geometry", {}).get("location", {})
                lat = location.get("lat")
                lng = location.get("lng")
                return f"Geocoded Address: {formatted_addr}\nLatitude: {lat}\nLongitude: {lng}"
            return f"Geocoding failed with status '{data.get('status')}': {data.get('error_message', 'No results found.')}"
    except Exception as e:
        return f"Error executing Geocoding API: {str(e)}"


def find_nearby_places(
    address: str = "",
    lat: float = 0.0,
    lng: float = 0.0,
    place_type: str = "store",
    radius_meters: float = 2000.0,
) -> str:
    """Finds nearby places (e.g. store, shopping_mall, electronics_store, clothing_store) near an address or coordinates.

    Args:
        address: Optional street address to search near (if provided, coordinates will be automatically derived).
        lat: Optional latitude coordinate (used if address is not specified).
        lng: Optional longitude coordinate (used if address is not specified).
        place_type: Type of place to search for (e.g. 'store', 'shopping_mall', 'electronics_store', 'clothing_store', 'cafe').
        radius_meters: Search radius in meters (default 2000.0).

    Returns:
        A formatted list of nearby places returning name, address, location coordinates, and types.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    target_lat = lat
    target_lng = lng

    if address and (target_lat == 0.0 and target_lng == 0.0):
        encoded_addr = urllib.parse.quote(address)
        geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_addr}&key={api_key}"
        try:
            req_geo = urllib.request.Request(geo_url, headers={"User-Agent": "ShopWise-AI/1.0"})
            with urllib.request.urlopen(req_geo, timeout=5) as res_geo:
                data_geo = json.loads(res_geo.read().decode("utf-8"))
                if data_geo.get("status") == "OK" and data_geo.get("results"):
                    loc = data_geo["results"][0].get("geometry", {}).get("location", {})
                    target_lat = loc.get("lat", 0.0)
                    target_lng = loc.get("lng", 0.0)
        except Exception:
            pass

    if target_lat == 0.0 and target_lng == 0.0:
        return "Error: Please provide a valid address or non-zero lat/lng coordinates."

    places_url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types",
    }
    payload = {
        "includedTypes": [place_type.lower().strip()],
        "locationRestriction": {
            "circle": {
                "center": {"latitude": target_lat, "longitude": target_lng},
                "radius": float(radius_meters),
            }
        },
        "maxResultCount": 5,
    }

    try:
        req_places = urllib.request.Request(
            places_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req_places, timeout=5) as res_places:
            data_places = json.loads(res_places.read().decode("utf-8"))
            places = data_places.get("places", [])
            if not places:
                return f"No nearby places of type '{place_type}' found within {radius_meters}m."

            formatted = []
            for p in places:
                display_name = p.get("displayName", {}).get("text", "Unknown Place")
                addr_text = p.get("formattedAddress", "N/A")
                loc_coords = p.get("location", {})
                lat_val = loc_coords.get("latitude")
                lng_val = loc_coords.get("longitude")
                formatted.append(
                    f"• Name: {display_name}\n"
                    f"  Address: {addr_text}\n"
                    f"  Location: Lat {lat_val}, Lng {lng_val}\n"
                    f"  Types: {', '.join(p.get('types', []))}"
                )

            return f"Nearby Places Results for '{place_type}':\n\n" + "\n\n".join(formatted)
    except Exception as e:
        return f"Error executing Places API (New): {str(e)}"


async def generate_product_image(prompt: str, tool_context: ToolContext) -> str:
    """Generates an e-commerce product image using the gemini-3.1-flash-lite-image model,
    saves it as a session artifact for the Playground, uploads the image bytes to public Cloud Storage,
    and returns its public https URL.

    Args:
        prompt: Detailed description of the product image to generate (e.g., 'Modern wireless headphones in matte black').
        tool_context: ADK ToolContext provided automatically by the runtime.

    Returns:
        The public https URL (https://storage.googleapis.com/<bucket>/<object>) of the generated image.
    """
    genai_client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location="global",
    )

    try:
        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        img_bytes = None
        mime_type = "image/jpeg"
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    img_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break

        if not img_bytes:
            return "Error: Failed to extract generated image bytes from model response."

        timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        ext = "png" if "png" in mime_type else "jpg"
        filename = f"product_{timestamp_str}.{ext}"

        # 1. Save as artifact for Playground Artifacts panel (awaited properly as async)
        artifact_part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload image bytes to public Cloud Storage bucket (no local file path writing)
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(img_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return public_url

    except Exception as e:
        return f"Error generating product image: {str(e)}"


async def generate_product_video(prompt: str, tool_context: ToolContext) -> str:
    """Generates a short e-commerce product showcase video for an item in ShopWise AI's domain
    (e.g., headphones, electronics, fashion, home decor) using the gemini-omni-flash-preview model in the global region,
    saves it as a session artifact for the Playground, uploads the video bytes to public Cloud Storage,
    and returns its public https URL.

    Args:
        prompt: Detailed description of the product video to generate (e.g., 'A 3-second product showcase video of wireless headphones').
        tool_context: ADK ToolContext provided automatically by the runtime.

    Returns:
        The public https URL (https://storage.googleapis.com/<bucket>/<object>) of the generated video.
    """
    genai_client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location="global",
    )

    try:
        response = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
            response_format={"type": "video"},
        )

        video_bytes = None
        mime_type = "video/mp4"

        if hasattr(response, "output_video") and response.output_video:
            out_vid = response.output_video
            if isinstance(out_vid, dict):
                b_data = out_vid.get("data")
                mime_type = out_vid.get("mime_type") or out_vid.get("mimeType") or mime_type
            else:
                b_data = getattr(out_vid, "data", None)
                mime_type = getattr(out_vid, "mime_type", mime_type)

            if b_data:
                if isinstance(b_data, str):
                    video_bytes = base64.b64decode(b_data)
                else:
                    video_bytes = b_data

        if not video_bytes:
            return "Error: Failed to extract generated video bytes from model response."

        timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"product_video_{timestamp_str}.mp4"

        # 1. Save as artifact for Playground Artifacts panel (awaited properly as async)
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload video bytes to public Cloud Storage bucket (no local file path writing)
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return public_url

    except Exception as e:
        return f"Error generating product video: {str(e)}"


# Build system prompt using A2uiSchemaManager version 0.8 and BasicCatalog
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "ShopWise AI, an intelligent e-commerce shopping assistant. "
        "You help users search for products in local inventory and external public catalogs, add new products, "
        "generate product images and product showcase videos, check live international currency exchange rates, geocode addresses, "
        "find nearby physical stores and places, run Python calculations safely in a code execution sandbox, "
        "and remember all user search queries, search history, and shopping preferences across sessions."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=code_executor,
    tools=[
        search_products,
        add_product,
        record_search,
        get_search_history,
        get_live_exchange_rate,
        fetch_external_catalog_products,
        geocode_address,
        find_nearby_places,
        generate_product_image,
        generate_product_video,
        PreloadMemoryTool(),
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
