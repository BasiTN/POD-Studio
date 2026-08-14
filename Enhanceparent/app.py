import os
import io
import json
import numpy as np
from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image
from google import genai
from google.genai import types

app = Flask(__name__)

# Initialize Gemini Client
client = genai.Client()

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def remove_white_background(pil_img, threshold=238):
    img = pil_img.convert("RGBA")
    data = np.array(img)
    r, g, b, a = data.T
    white_areas = (r >= threshold) & (g >= threshold) & (b >= threshold)
    data[..., 3][white_areas.T] = 0
    return Image.fromarray(data)

def fit_to_300dpi_canvas(img, target_w=4500, target_h=5400):
    scale = min(target_w / img.width, target_h / img.height)
    new_w, new_h = int(img.width * scale), int(img.height * scale)
    resized_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    canvas.paste(resized_img, ((target_w - new_w) // 2, (target_h - new_h) // 2), resized_img)
    return canvas

# ==========================================
# ROUTES
# ==========================================
@app.route("/")
def index():
    return render_template("index.html")

# --- TOOL 1: UNIFIED GRAPHIC ENHANCER ---
@app.route("/process-enhancer", methods=["POST"])
def process_enhancer():
    if "file" not in request.files: return "No file uploaded", 400
    file = request.files["file"]
    
    do_transparency = request.form.get("transparency") == "true"
    do_enhancement = request.form.get("enhancement") == "true"
    do_dpi_scale = request.form.get("dpiscale") == "true"

    img = Image.open(io.BytesIO(file.read())).convert("RGBA")

    # 1. Background removal
    if do_transparency:
        img = remove_white_background(img)

    # 2. 4x Upscale
    if do_enhancement:
        w, h = img.size
        img = img.resize((w * 4, h * 4), Image.Resampling.LANCZOS)

    # 3. Canvas format to 4500x5400 @ 300 DPI
    if do_dpi_scale:
        img = fit_to_300dpi_canvas(img)

    buf = io.BytesIO()
    if do_dpi_scale:
        img.save(buf, format="PNG", dpi=(300, 300))
    else:
        img.save(buf, format="PNG", quality=100)

    buf.seek(0)
    return send_file(buf, mimetype="image/png", as_attachment=True, download_name="enhanced_design.png")


# --- TOOL 2: COLOR VARIANT GENERATOR ---
@app.route("/process-colorvariant", methods=["POST"])
def process_colorvariant():
    if "file" not in request.files: return "No file uploaded", 400
    file = request.files["file"]
    target_color = request.form.get("color", "#FFFFFF")
    
    img = Image.open(io.BytesIO(file.read())).convert("RGBA")
    hex_color = target_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    data = np.array(img)
    mask = data[..., 3] > 10
    data[mask, 0], data[mask, 1], data[mask, 2] = rgb[0], rgb[1], rgb[2]
    
    buf = io.BytesIO()
    Image.fromarray(data).save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", as_attachment=True, download_name="color_variant.png")


# --- TOOL 3: AI FEMALE MOCKUP PROMPT STUDIO (100% FREE) ---
@app.route("/process-mockup", methods=["POST"])
def process_mockup():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]

    try:
        pil_img = Image.open(io.BytesIO(file.read())).convert("RGB")

        prompt = """
        You are an expert fashion photographer and AI prompt engineer for Print-on-Demand products.
        Analyze this graphic/T-shirt image and return a JSON object with EXACTLY this structure:
        {
            "vibe_analysis": "A brief 2-sentence breakdown of the graphic's aesthetic, color scheme, and target audience style.",
            "mockups": [
                {
                    "setting": "Setting Name (e.g. Sunlit Park / Garden)",
                    "prompt": "Full 4K photorealistic prompt featuring a young female model wearing a t-shirt with this exact design, detailed lighting, camera lens, background, mood, photorealistic portrait --ar 1:1"
                },
                {
                    "setting": "Setting Name (e.g. Cozy Library / Cafe)",
                    "prompt": "Full 4K photorealistic prompt featuring a young female model..."
                },
                {
                    "setting": "Setting Name (e.g. Urban Street / City Walk)",
                    "prompt": "Full 4K photorealistic prompt featuring a young female model..."
                },
                {
                    "setting": "Setting Name (e.g. Vacation / Botanical)",
                    "prompt": "Full 4K photorealistic prompt featuring a young female model..."
                }
            ]
        }
        Only return clean JSON. Do not wrap in extra markdown text outside JSON.
        """

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[pil_img, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        data = json.loads(response.text)
        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- TOOL 4: AI PINTEREST SEO ANALYZER ---
import requests
from bs4 import BeautifulSoup

def extract_url_details(url):
    """Scrapes meta tags and product text from e-commerce product URLs."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract Page Title & Meta Descriptions
    page_title = soup.title.string.strip() if soup.title else ""
    meta_desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    meta_desc = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""

    # Extract body content snippets
    paragraphs = [p.get_text().strip() for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'span']) if len(p.get_text().strip()) > 20]
    body_snippet = " ".join(paragraphs[:10])

    return f"Product Title: {page_title}\nMeta Description: {meta_desc}\nProduct Details: {body_snippet[:1500]}"


# --- TOOL 4: AI PINTEREST SEO ANALYZER ---
@app.route("/process-pinterest-seo", methods=["POST"])
def process_pinterest_seo():
    product_url = request.form.get("url", "").strip()
    file = request.files.get("file")

    if not product_url and not file:
        return jsonify({"error": "Please provide either a Product URL or an Image file."}), 400

    try:
        contents = []

        # If URL provided, scrape and analyze page text
        if product_url:
            scraped_details = extract_url_details(product_url)
            contents.append(f"Analyze this product link info for Pinterest SEO:\n{scraped_details}")
        
        # If image uploaded, include image data
        if file:
            pil_img = Image.open(io.BytesIO(file.read())).convert("RGB")
            contents.append(pil_img)

        prompt = """
        You are a Pinterest SEO expert for Print-on-Demand and E-commerce products.
        Analyze the provided product information and return a JSON object with EXACTLY this structure:
        {
            "titles": [
                "Title 1 (70 to 80 characters long, catchy, high-search volume)",
                "Title 2 (70 to 80 characters long, catchy, high-search volume)",
                "Title 3 (70 to 80 characters long, catchy, high-search volume)"
            ],
            "description": "An engaging, high-converting product description (around 350-450 characters). Highlight key features and hook the buyer. AT THE VERY BOTTOM OF THIS DESCRIPTION, ADD A DOUBLE NEWLINE AND INCLUDE 6 TO 8 HIGH-VOLUME RELEVANT PINTEREST HASHTAGS (e.g. #giftideas #aesthetic #streetwear #fashion).",
            "alt_text": "Clear, concise descriptive Alt Text for visually impaired readers describing the product style, colors, and subject matter."
        }
        Do not output markdown code blocks outside JSON. Only return clean JSON.
        """
        contents.append(prompt)

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        data = json.loads(response.text)
        return jsonify(data)

    except Exception as e:
        return jsonify({"error": f"Failed to analyze product: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

# Add this check in your backend script before sending to the LLM
print("--- SCRAPED DATA PASSED TO AI ---")
print(scraped_text)
print("----------------------------------")