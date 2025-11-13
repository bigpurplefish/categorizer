# Voice and Tone Guidelines for Product Descriptions

This document defines the voice and tone standards for product descriptions (`body_html`) in the Shopify Product Uploader.

## Core Requirements

Product descriptions in `body_html` must **always** be:

1. **Newly written in natural language** – Not pasted or stitched from source text
2. **Second-person voice** – Directly addressing the customer
3. **Imperative-first phrasing** – Prefer commands (e.g., "Support...", "Encourage...", "Keep feeding tidy...") instead of beginning every sentence with "You..."
4. **Factually based** – Use content currently in this key only as reference material to inspire new copy
5. **Original and non-templated** – Avoid catalog phrasing, filler words, or boilerplate
6. **Never copied verbatim** – Do not copy raw sentences, benefit bullets, ingredient lists, or nutrition analysis directly
7. **Not concatenated** – Never concatenate raw fragments into templated sentences
8. **Properly encoded** – Ensure human-readable punctuation only (apostrophes, quotes, dashes). No encoded escape sequences such as `\u2019`
9. **Unique across similar products** – Products of the same type (e.g., multiple pavers) must draw from variant phrasing pools for openings and closings, so no two records repeat the same consecutive 7+ words

---

## Tone by Department

### Pet Supplies
**Tone:** Friendly and empathetic

- Speak as if to a caring pet parent
- Highlight comfort, behavior, health, and bonding moments
- Avoid generic phrases like "premium" or "must-have"

**Examples:**

✅ **Good:**
- "Soothe your dog's itchy skin with this aloe-rich shampoo that comforts irritated spots and makes snuggle time feel even better."
- "Keep mealtime calm and mess-free with a non-skid bowl that stays put while your dog eats — and cleans up easily afterward."
- "Support your cat's recovery with this gentle supplement that helps them regain energy and feel more like themselves again."

❌ **Bad:**
- "This premium shampoo is formulated for all dogs."
- "Durable metal bowl with anti-tip base."

---

### Livestock and Farm
**Tone:** Supportive and plainspoken

- Speak kindly and directly
- Focus on health, care, and ease for the caretaker
- Avoid clinical or generic livestock terminology

**Examples:**

✅ **Good:**
- "Help your calf grow strong with this milk replacer designed to support early development and easier digestion."
- "Protect your goats from biting pests with this easy-to-apply pour-on formula that keeps them calm and comfortable."
- "Keep your horse hydrated on long summer days with this electrolyte blend that mixes right into feed or water."

❌ **Bad:**
- "This livestock supplement supports hydration and growth."
- "All-in-one formula for farm animals."

---

### Landscape and Construction
**Tone:** Direct and professional

- Focus on durability, efficiency, and performance
- Avoid decorative or flowery language

**Examples:**

✅ **Good:**
- "Compact your gravel base quickly with this gas-powered plate compactor built for pro-grade performance."
- "Prevent shifting and erosion with this contractor-grade paver edge restraint system."

❌ **Bad:**
- "This edge restraint is a high-quality solution for your paving needs."
- "The compacting tool features a sturdy frame and ergonomic handle."

---

### Lawn and Garden
**Tone:** Upbeat and hobbyist-friendly

- Highlight enjoyment, natural benefits, and ease of use

**Examples:**

✅ **Good:**
- "Feed your vegetable garden with this slow-release fertilizer that boosts root strength and improves yields naturally."
- "Decorate your garden path with this wind chime that brings soft, melodic tones to your backyard."

❌ **Bad:**
- "This fertilizer is ideal for gardens and flowers."
- "Enjoy the sound of this wind chime in your home or garden."

---

### Home and Gift
**Tone:** Warm and lifestyle-oriented

- Emphasize sensory appeal (scent, texture, look) and giftability

**Examples:**

✅ **Good:**
- "Light up your holiday table with this cinnamon-scented soy candle in a frosted glass jar."
- "Celebrate birthdays with this customizable pet-themed gift card."

❌ **Bad:**
- "This decorative candle is made of high-quality wax."
- "A must-have for holiday decor."

---

### Hunting and Fishing
**Tone:** Rugged and practical

- Prioritize performance, reliability, and field use
- Respect tradition and purpose-driven tone

**Examples:**

✅ **Good:**
- "Mask your scent before the hunt with this earth-scent spray designed for deer hunters in wooded terrain."
- "Attract more bucks to your plot with this apple-flavored mineral block packed with key supplements."

❌ **Bad:**
- "This scent spray is formulated for hunters and outdoor use."
- "Great for deer hunting."

---

## Writing Checklist

Before submitting a product description, verify:

- [ ] Written in second-person voice
- [ ] Uses imperative-first phrasing (not excessive "You..." starts)
- [ ] Contains no raw copied sentences from source material
- [ ] Contains no filler words like "premium," "must-have," "high-quality"
- [ ] Tone matches the department guidelines
- [ ] No encoded characters (check for `\u` escape sequences)
- [ ] Unique opening compared to similar products (no 7+ word repetitions)
- [ ] Focuses on benefits and use cases, not just features
- [ ] Sounds natural when read aloud

---

## Usage in Uploader

The Claude API integration uses these guidelines to:
1. Analyze the current product description
2. Determine the appropriate department tone
3. Rewrite the description following voice and tone standards
4. Ensure uniqueness across similar products in the same batch
