/* UI translations stay local; document content and generated answers are preserved. */
const translations = {
  '01 / BAZA DE CUNOȘTINȚE': '01 / KNOWLEDGE BASE',
  'Documentele tale.': 'Your documents.', 'Contextul tău.': 'Your context.',
  'Încarcă documentația tehnică. Răspunsurile pornesc de la sursă.': 'Upload technical documentation. Answers start at the source.',
  'Adaugă documente': 'Add documents',
  'PDF, Markdown, TXT · max. 20 MiB / fișier': 'PDF, Markdown, TXT · max. 20 MiB / file',
  'BIBLIOTECĂ': 'LIBRARY', 'Stocare locală · SQLite': 'Local storage · SQLite',
  'AWS S3: backup opțional din terminal.': 'AWS S3: optional backup from the terminal.',
  'Verificare Ollama…': 'Checking Ollama…', '02 / ASISTENT TEHNIC': '02 / TECHNICAL ASSISTANT',
  'Mai puțin căutat.': 'Less searching.', 'Mai mult context.': 'More context.',
  'Întreabă documentația despre infrastructură, livrare și securitate.': 'Ask your documentation about infrastructure, delivery and security.',
  'Verifică răspunsurile direct în fragmentele citate.': 'Check answers against the cited excerpts.',
  'Pornește Ollama și descarcă modelele configurate în': 'Start Ollama and download the models configured in',
  '. Apoi apasă': '. Then select', 'Verifică din nou': 'Check again',
  'ÎNCEPE CU O ÎNTREBARE': 'START WITH A QUESTION',
  'Care sunt pașii de deployment descriși în documente?': 'What deployment steps are described in the documents?',
  'Ce recomandări de securitate apar în documentație?': 'What security recommendations appear in the documentation?',
  'Întrebarea ta': 'Your question', 'Întreabă ↗': 'Ask ↗',
  'Ex.: Cum configurez un NetworkPolicy conform documentației?': 'E.g.: How do I configure a NetworkPolicy according to the documentation?',
  'Procesare locală. Răspunsurile AI pot conține erori; verifică sursele. Fiecare întrebare este independentă.': 'Local processing. AI answers may contain errors; check the sources. Each question is independent.',
  'Cerere invalidă. Verifică datele introduse.': 'Invalid request. Check your input.',
  '● OLLAMA CONECTAT': '● OLLAMA CONNECTED', '◌ MODELE LIPSĂ': '◌ MODELS MISSING', '◌ OLLAMA OPRIT': '◌ OLLAMA OFFLINE',
  'Niciun document importat.': 'No documents imported.',
  'deja indexat': 'already indexed', 'TU / ÎNTREBARE': 'YOU / QUESTION', 'OpsAtlas / RĂSPUNS': 'OpsAtlas / ANSWER',
  'Caut în documente și pregătesc răspunsul…': 'Searching documents and preparing an answer…',
  'Modelul nu a furnizat citări valide pentru toate referințele. Verifică fragmentele de mai jos.': 'The model did not provide valid citations for all references. Check the excerpts below.',
  'PDF criptat: exportă o copie necriptată.': 'Encrypted PDF: export an unencrypted copy.',
  'Maximum 1000 de pagini per PDF.': 'Maximum 1000 pages per PDF.',
  'PDF invalid sau imposibil de procesat.': 'Invalid or unreadable PDF.',
  'Salvează fișierul text în UTF-8.': 'Save the text file as UTF-8.',
  'Sunt acceptate doar PDF, Markdown și TXT.': 'Only PDF, Markdown and TXT are supported.',
  'Document prea mare: maximum 3000 de fragmente.': 'Document too large: maximum 3000 chunks.',
  'Document fără text. PDF-urile scanate necesită OCR separat.': 'No text found. Scanned PDFs require separate OCR processing.',
  'Dimensiuni embeddings incompatibile. Reindexează documentele.': 'Incompatible embedding dimensions. Reindex the documents.',
  'Ollama indisponibil sau model lipsă. Verifică Ollama și modelele configurate.': 'Ollama unavailable or model missing. Check Ollama and the configured models.',
  'Răspuns embeddings invalid.': 'Invalid embedding response.',
  'Modelul a returnat un răspuns gol.': 'The model returned an empty answer.',
  'Fișier gol sau mai mare de 20 MiB.': 'File is empty or exceeds 20 MiB.',
  'Document indexat cu alt model. Șterge-l și importă-l din nou.': 'Document indexed with a different model. Delete and reimport it.',
  'Embeddings incomplete sau incompatibile.': 'Incomplete or incompatible embeddings.',
  'Importă mai întâi documentele în baza de cunoștințe.': 'Import documents into the knowledge base first.',
  'Modelul de embeddings s-a schimbat. Șterge și reimportă documentele înainte de căutare.': 'The embedding model has changed. Delete and reimport the documents before searching.',
  'Nu am găsit fragmente suficient de relevante în documentele importate.': 'No sufficiently relevant excerpts were found in the imported documents.',
  'Token local invalid. Reîncarcă pagina.': 'Invalid local token. Reload the page.',
  'Eroare internă. Verifică terminalul aplicației.': 'Internal error. Check the application terminal.',
  'Maximum 20 MiB per fișier.': 'Maximum 20 MiB per file.',
  'Document inexistent.': 'Document not found.', 'Introdu o întrebare.': 'Enter a question.'
};
let language = 'ro';
try { language = localStorage.getItem('dk-language') === 'en' ? 'en' : 'ro'; } catch {}
function t(text) {
  if (language === 'en') return translations[text] || text;
  const messages = {
    'An import is already running. Wait for it to finish.': 'Un import rulează deja. Așteaptă finalizarea lui.',
    'Empty file.': 'Fișier gol.',
    'Only PDF, Markdown and TXT are supported.': 'Sunt acceptate doar PDF, Markdown și TXT.',
    'Invalid or unreadable PDF.': 'PDF invalid sau imposibil de procesat.',
    'Encrypted PDF. Export an unencrypted copy.': 'PDF criptat. Exportă o copie necriptată.',
    'Save the text file as UTF-8.': 'Salvează fișierul text în UTF-8.',
    'No text found. Scanned PDFs require separate OCR processing.': 'Document fără text. PDF-urile scanate necesită OCR separat.',
    'Document indexed with another model. Delete and reimport it.': 'Document indexat cu alt model. Șterge-l și importă-l din nou.',
    'Incomplete embeddings.': 'Embeddings incomplete.',
    'Incompatible embeddings.': 'Embeddings incompatibile.',
    'Internal error. Check the application terminal.': 'Eroare internă. Verifică terminalul aplicației.'
  };
  if (messages[text]) return messages[text];
  return text.replace(/^Maximum (\d+) MiB per file\.$/, 'Maximum $1 MiB per fișier.')
    .replace(/^Maximum (\d+) pages per PDF\.$/, 'Maximum $1 de pagini per PDF.')
    .replace(/^Maximum (\d+) chunks per document\.$/, 'Maximum $1 de fragmente per document.');
}
const staticLabels = [];
function initLanguage() {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (translations[node.textContent.trim()]) staticLabels.push({node, original: node.textContent});
  }
  const placeholder = document.querySelector('#question').placeholder;
  function applyLanguage() {
    document.documentElement.lang = language;
    for (const {node, original} of staticLabels) {
      node.textContent = original.replace(original.trim(), t(original.trim()));
    }
    document.querySelector('#question').placeholder = t(placeholder);
    document.querySelectorAll('[data-language]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.language === language));
    });
  }
  document.querySelector('#language').addEventListener('click', event => {
    const button = event.target.closest('[data-language]');
    if (!button || document.querySelector('#language').disabled || button.dataset.language === language) return;
    language = button.dataset.language;
    try { localStorage.setItem('dk-language', language); } catch {}
    applyLanguage();
    document.dispatchEvent(new Event('languagechange'));
  });
  applyLanguage();
}
initLanguage();
