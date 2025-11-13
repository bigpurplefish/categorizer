# Product Taxonomy

> **⚠️ DEPRECATED**: This local copy is outdated and should not be used.
>
> **Use the shared documentation instead**: `/Users/moosemarketer/Code/shared-docs/python/PRODUCT_TAXONOMY.md`
>
> The shared version includes:
> - Purchase and fulfillment options
> - Updated category structures
> - Packaging weight references
> - Complete tag formats
>
> This file is kept for reference only and will be removed in a future update.

---

This document defines the internal product taxonomy used for categorizing products in the Shopify Product Uploader.

## Taxonomy Structure

The taxonomy consists of three levels:
- **Department** (Level 1): Stored in the `product_type` field
- **Category** (Level 2): Stored as a tag without prefix
- **Subcategory** (Level 3): Stored as a tag without prefix

## Complete Product Taxonomy

### 1. LANDSCAPE AND CONSTRUCTION

**Product Type:** `Landscape and Construction`

#### Aggregates
- **Tags:** `Aggregates`
- **Subcategories:**
  1. Stone
  2. Soil
  3. Mulch
  4. Sand

#### Pavers and Hardscaping
- **Tags:** `Pavers and Hardscaping`
- **Subcategories:**
  1. **Slabs**
     - Tags: `Pavers and Hardscaping`, `Slabs`
  2. **Pavers**
     - Tags: `Pavers and Hardscaping`, `Pavers`
     - Additional tag: `Permeable` (for permeable pavers)
  3. **Retaining Walls**
     - Tags: `Pavers and Hardscaping`, `Retaining Walls`
  4. **Wall Caps**
     - Tags: `Pavers and Hardscaping`, `Wall Caps`
  5. **Steps & Treads**
     - Tags: `Pavers and Hardscaping`, `Steps & Treads`
  6. **Edging & Borders**
     - Tags: `Pavers and Hardscaping`, `Edging & Borders`
  7. **Joint Sand & Polymeric Sand**
     - Tags: `Pavers and Hardscaping`, `Joint Sand & Polymeric Sand`
  8. **Sealers & Cleaners**
     - Tags: `Pavers and Hardscaping`, `Sealers & Cleaners`
  9. **Base Materials & Geotextiles**
     - Tags: `Pavers and Hardscaping`, `Base Materials & Geotextiles`
  10. **Accessories**
      - Tags: `Pavers and Hardscaping`, `Accessories`

#### Paving Tools & Equipment
- **Tags:** `Paving Tools & Equipment`
- **Subcategories:**
  1. Hand Tools
  2. Compactors
  3. Screeds

#### Paving & Construction Supplies
- **Tags:** `Paving & Construction Supplies`
- **Subcategories:**
  1. Edging
  2. Adhesives
  3. Spikes
  4. Sealers

---

### 2. LAWN AND GARDEN

**Product Type:** `Lawn and Garden`

#### Garden Tools
- **Tags:** `Garden Tools`
- **Subcategories:**
  1. Shovels
  2. Wheelbarrows
  3. Pruners
  4. Gloves

#### Garden Supplies
- **Tags:** `Garden Supplies`
- **Subcategories:**
  1. Fertilizers
  2. Soil Conditioners
  3. Planters
  4. Watering Systems

#### Garden Decor
- **Tags:** `Garden Decor`
- **Subcategories:**
  1. Flags
  2. Stakes
  3. Chimes
  4. Statues

---

### 3. HOME AND GIFT

**Product Type:** `Home and Gift`

#### Home Decor
- **Tags:** `Home Decor`
- **Subcategories:**
  1. Candles
  2. Wall Art
  3. Seasonal Decorations

#### Gifts
- **Tags:** `Gifts`
- **Subcategories:**
  1. Gift Cards
  2. Novelty Items
  3. Themed Gifts

---

### 4. PET SUPPLIES

**Product Type:** `Pet Supplies`

#### Dogs
- **Tags:** `Dogs`
- **Subcategories:**
  1. Bedding
  2. Carriers
  3. Chews
  4. Cleaning
  5. Collars
  6. Crates
  7. Food
  8. Grooming
  9. Harnesses
  10. Training Tools
  11. Toys
  12. Treats
  13. Waste
  14. Accessories

#### Cats
- **Tags:** `Cats`
- **Subcategories:**
  1. Bedding
  2. Carriers
  3. Cleaning
  4. Collars
  5. Food
  6. Grooming
  7. Harnesses
  8. Toys
  9. Treats
  10. Waste
  11. Accessories

#### Birds
- **Tags:** `Birds`
- **Subcategories:**
  1. Cages
  2. Health
  3. Seeds
  4. Toys
  5. Treats
  6. Accessories

#### Small Pets
- **Tags:** `Small Pets`
- **Note:** Includes rabbits, guinea pigs, hamsters
- **Subcategories:**
  1. Bedding
  2. Cages
  3. Food
  4. Accessories

---

### 5. LIVESTOCK AND FARM

**Product Type:** `Livestock and Farm`

#### Horses
- **Tags:** `Horses`
- **Subcategories:**
  1. Feed (includes hay)
  2. Health
  3. Tack & Equipment
  4. Accessories

#### Chickens
- **Tags:** `Chickens`
- **Subcategories:**
  1. Feed
  2. Supplies (coops, feeders, waterers)
  3. Accessories

#### Goats
- **Tags:** `Goats`
- **Subcategories:**
  1. Feed (includes hay)
  2. Health
  3. Accessories

#### Sheep
- **Tags:** `Sheep`
- **Subcategories:**
  1. Feed (includes hay)
  2. Health
  3. Accessories

#### General Farm Supplies
- **Tags:** `General Farm Supplies`
- **Subcategories:**
  1. Buckets
  2. Scoops
  3. Fencing
  4. Tools

---

### 6. HUNTING AND FISHING

**Product Type:** `Hunting and Fishing`

#### Deer
- **Tags:** `Deer`
- **Subcategories:**
  1. Attractants
  2. Minerals & Supplements
  3. Gear
  4. Food Plots
  5. Scent Control

---

## Shopify Field Mapping

| Taxonomy Level | Shopify Field | Example |
|----------------|---------------|---------|
| Level 1 (Department) | `product_type` | "Landscape and Construction" |
| Level 2 (Category) | First tag | "Pavers and Hardscaping" |
| Level 3 (Subcategory) | Second tag | "Slabs" |

**Example Product:**
- **Department:** Landscape and Construction
- **Category:** Pavers and Hardscaping
- **Subcategory:** Slabs
- **Shopify Fields:**
  - `product_type`: "Landscape and Construction"
  - `tags`: ["Pavers and Hardscaping", "Slabs"]

---

## Usage in Uploader

The Claude API integration uses this taxonomy to:
1. Analyze product titles and descriptions
2. Assign appropriate Department (product_type)
3. Assign appropriate Category and Subcategory (tags)
4. Ensure consistent categorization across all products
