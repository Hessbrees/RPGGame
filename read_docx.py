from docx import Document

# Odczytaj plik .docx
doc = Document('ProjektDyplomowy_MarceliLenart.docx')

print("=" * 80)
print("ZAWARTOŚĆ DOKUMENTU")
print("=" * 80)
print()

# Wyświetl wszystkie paragrafy
for i, para in enumerate(doc.paragraphs, 1):
    text = para.text.strip()
    if text:  # Wyświetl tylko niepuste paragrafy
        print(f"{text}")
        print()

# Wyświetl zawartość tabel, jeśli istnieją
if doc.tables:
    print("\n" + "=" * 80)
    print("TABELE W DOKUMENCIE")
    print("=" * 80)
    for i, table in enumerate(doc.tables, 1):
        print(f"\n--- Tabela {i} ---")
        for row in table.rows:
            row_text = " | ".join([cell.text.strip() for cell in row.cells])
            if row_text.strip():
                print(row_text)
