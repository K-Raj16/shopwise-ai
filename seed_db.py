#!/usr/bin/env python3
"""Seed script for ShopWise AI Firestore database."""

from google.cloud import firestore

# IMPORTANT: Hardcoded project ID as required by Agent Platform
PROJECT_ID = "qwiklabs-gcp-03-e5b049a0a94d"

db = firestore.Client(project=PROJECT_ID)

PRODUCTS = [
    {
        "id": "prod_001",
        "name": "Aura Sound Pro Headphones",
        "category": "Electronics",
        "price": 249.99,
        "description": "Premium wireless over-ear headphones with active noise cancellation and 30-hour battery life.",
        "rating": 4.8,
        "in_stock": True,
        "tags": ["audio", "wireless", "headphones", "electronics"],
    },
    {
        "id": "prod_002",
        "name": "ErgoFlex Ergonomic Office Chair",
        "category": "Furniture",
        "price": 320.00,
        "description": "Breathable mesh office chair with adjustable lumbar support and 3D armrests.",
        "rating": 4.6,
        "in_stock": True,
        "tags": ["office", "furniture", "ergonomic", "chair"],
    },
    {
        "id": "prod_003",
        "name": "UltraFit Smart Watch Series 5",
        "category": "Electronics",
        "price": 179.50,
        "description": "Waterproof fitness tracker with heart rate monitor, sleep tracking, and AMOLED display.",
        "rating": 4.5,
        "in_stock": True,
        "tags": ["wearable", "smartwatch", "fitness", "electronics"],
    },
    {
        "id": "prod_004",
        "name": "Artisan Ceramic Drip Coffee Maker",
        "category": "Kitchen",
        "price": 85.00,
        "description": "Handcrafted ceramic pour-over coffee set with thermal glass carafe.",
        "rating": 4.9,
        "in_stock": True,
        "tags": ["kitchen", "coffee", "ceramic", "home"],
    },
    {
        "id": "prod_005",
        "name": "Urban Explorer Waterproof Backpack",
        "category": "Apparel",
        "price": 110.00,
        "description": "Durable 25L commuter backpack with padded laptop sleeve and water-resistant zippers.",
        "rating": 4.7,
        "in_stock": False,
        "tags": ["backpack", "travel", "bags", "apparel"],
    },
]

SEARCH_HISTORY = [
    {
        "query": "noise canceling wireless headphones",
        "category": "Electronics",
        "timestamp": "2026-09-28T04:30:00Z",
    },
    {
        "query": "ergonomic desk chair for home office",
        "category": "Furniture",
        "timestamp": "2026-09-28T05:00:00Z",
    },
]


def seed_database():
    print(f"Seeding Firestore database for project '{PROJECT_ID}'...")

    # Seed products
    for product in PRODUCTS:
        doc_ref = db.collection("products").document(product["id"])
        doc_ref.set(product)
        print(f"  [+] Seeded product: {product['id']} - {product['name']}")

    # Seed initial search history
    for idx, history in enumerate(SEARCH_HISTORY):
        doc_id = f"hist_{idx+1:03d}"
        doc_ref = db.collection("search_history").document(doc_id)
        doc_ref.set(history)
        print(f"  [+] Seeded search history: {doc_id} - '{history['query']}'")

    print("Firestore database seeded successfully!")


if __name__ == "__main__":
    seed_database()
