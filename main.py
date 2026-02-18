from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import fitz  # pymupdf
import io
import base64

app = FastAPI(title="PDF Reference Finder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Stockage en mémoire du catalogue
catalogue = {
    "index": {},       # référence -> numéro de page
    "pdf_bytes": None, # le PDF en mémoire pour générer les images
    "total_pages": 0
}


@app.get("/status")
def status():
    if catalogue["pdf_bytes"] is None:
        return {"catalogue_charge": False, "message": "Aucun catalogue chargé"}
    return {
        "catalogue_charge": True,
        "total_pages": catalogue["total_pages"],
        "mots_indexes": len(catalogue["index"])
    }


@app.post("/indexer")
async def indexer_catalogue(fichier: UploadFile = File(...)):
    """
    Upload le catalogue PDF une seule fois.
    L'API lit toutes les pages et crée un index en mémoire.
    """
    contenu = await fichier.read()
    index = {}

    with pdfplumber.open(io.BytesIO(contenu)) as pdf:
        total_pages = len(pdf.pages)
        for numero, page in enumerate(pdf.pages, start=1):
            texte = page.extract_text()
            if texte:
                for ligne in texte.split("\n"):
                    ligne_propre = ligne.strip()
                    if ligne_propre:
                        cle = ligne_propre.lower()
                        if cle not in index:
                            index[cle] = numero

    catalogue["index"] = index
    catalogue["pdf_bytes"] = contenu
    catalogue["total_pages"] = total_pages

    return {
        "succes": True,
        "total_pages": total_pages,
        "mots_indexes": len(index),
        "message": "Catalogue indexé avec succès"
    }


@app.get("/chercher")
def chercher_reference(reference: str):
    """
    Cherche une référence dans le catalogue indexé.
    Retourne le numéro de page et l'image de la page en base64.
    """
    if catalogue["pdf_bytes"] is None:
        raise HTTPException(status_code=400, detail="Aucun catalogue chargé. Appelez d'abord /indexer")

    reference_lower = reference.lower().strip()
    page_trouvee = None

    # Recherche exacte d'abord
    for cle, page in catalogue["index"].items():
        if reference_lower in cle:
            page_trouvee = page
            break

    if page_trouvee is None:
        return {
            "reference": reference,
            "trouvee": False,
            "page": None,
            "image_base64": None
        }

    # Convertit la page en image via pymupdf
    doc = fitz.open(stream=catalogue["pdf_bytes"], filetype="pdf")
    page_pdf = doc[page_trouvee - 1]  # pymupdf commence à 0
    mat = fitz.Matrix(2, 2)  # zoom x2 pour une bonne qualité
    pix = page_pdf.get_pixmap(matrix=mat)
    image_bytes = pix.tobytes("png")
    doc.close()

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    return {
        "reference": reference,
        "trouvee": True,
        "page": page_trouvee,
        "total_pages": catalogue["total_pages"],
        "image_base64": image_base64
    }
