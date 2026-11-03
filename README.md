# OpsAtlas — RAG local, backup AWS opțional

Aplicație Python independentă, inspirată de fluxul proiectului [rag-devops-assistant](https://github.com/sainathmitalakar/rag-devops-assistant). Importă PDF/Markdown/TXT, generează embeddings în Ollama și răspunde cu fragmente citate. Nu execută comenzi și nu trimite întrebări către API-uri AI externe.

Numele aplicației și numele recomandat pentru repository sunt **OpsAtlas** / `opsatlas`. Directorul local poate fi redenumit ulterior: oprește serverul, închide terminalele din proiect, redenumește `web-app` în `opsatlas` și redeschide folderul în IDE. Căile aplicației sunt relative; recreează `.venv` în noul director deoarece mediile virtuale Python nu sunt portabile. Dacă ai configurat căi absolute în `.env`, actualizează-le. Documentele locale din `docs/`, baza din `data/` și `.env` sunt excluse din Git.

## Pornire pe Windows

Ai nevoie de Python 3.12+ și [Ollama](https://ollama.com/download). Din PowerShell, în acest director:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
ollama pull qwen3:14b
ollama pull embeddinggemma:300m
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Deschide **http://127.0.0.1:8000**. Ollama trebuie să ruleze (aplicația desktop sau `ollama serve`). Dacă ai deja un model de chat potrivit, pune numele exact din `ollama list` în `CHAT_MODEL`, fără alt download. Configurația de pornire folosește qwen3:14b; un model mai mare poate fi evaluat ulterior pe propriile întrebări.

În acest checkout, `.env` local este configurat cu modelul deja instalat `qwen2.5:7b`, pentru a verifica funcționarea fără descărcarea unui alt model de chat. Nu suprascrie `.env` dacă dorești să păstrezi această configurație. `.env.example` rămâne șablonul pentru o instalare nouă.

În Git Bash, interpreterul este `./.venv/Scripts/python.exe`. Nu este necesară activarea mediului virtual. Dacă Windows raportează `No such file or directory` în Documents, verifică Protection history pentru Controlled folder access. Alternativ folosește un director de proiect sub `C:\Users\cod_ec\source`.

Descărcarea pachetelor și a modelelor necesită internet. După aceea aplicația funcționează local, fără CDN sau fonturi externe. Ollama poate avea propriile verificări de actualizare; pentru o stație complet izolată aplică reguli de egress la nivelul sistemului.

## Utilizare și limite

Interfața are un selector Română / English în partea de sus. Preferința este păstrată în browser. Limba interfeței nu traduce documentele sau răspunsurile existente; modelul răspunde în limba întrebării.

- Importă documentele din interfață. Implicit: maximum **100 MiB, 5000 de pagini și 30000 de fragmente per document**. PDF-urile scanate necesită OCR separat.
- Limitele se configurează în `.env` prin `MAX_UPLOAD_MB=100`, `MAX_PDF_PAGES=5000` și `MAX_DOCUMENT_CHUNKS=30000`. Repornește serverul după modificare; pagina preia limita de upload din backend. Unitatea este MiB (1024 × 1024 octeți).
- Uploadul primește HTTP 202 și un `job_id`; progresul și erorile se citesc din `GET /api/imports`. Pagina afișează numărul de fragmente indexate și, pentru PDF, paginile citite. Acestea nu reprezintă procentul total de lucru: generarea embeddings continuă după citirea unei pagini. Poți folosi chatul în timpul indexării și poți reîncărca pagina pentru a regăsi progresul.
- Se execută un singur import simultan; fișierele selectate împreună sunt trimise pe rând din browser. Rulează serverul cu un singur worker. Stările importurilor sunt păstrate în memoria procesului (ultimele 100); un restart pierde progresul și necesită retrimiterea importurilor nefinalizate. Importurile deja finalizate rămân în SQLite. Închiderea normală a serverului așteaptă importul activ. Fișierele selectate, dar încă netrimise din browser, trebuie selectate din nou după reîncărcarea paginii.
- Fișierul uploadat și indexul intermediar sunt stocate temporar pe disc, embeddings sunt generate în loturi de 16, iar publicarea documentului în index este atomică. Textul este citit în blocuri, PDF-ul pagină cu pagină; biblioteca PDF poate totuși aloca multă memorie pentru pagini complexe/decomprimate. Dimensiunea fișierului nu este o limită strictă a memoriei folosite. Păstrează suficient spațiu liber pentru upload, indexul intermediar și baza finală. La oprire forțată pot rămâne directoare temporare `tmp*` în `DATA_DIR`; inspectează-le și elimină-le doar cu serverul oprit.
- Documentele identice sunt deduplicate după SHA-256. Importul este atomic; un eșec embeddings nu lasă documente parțiale.
- Întrebările sunt independente. Interfața păstrează conversația numai până la reîncărcarea paginii; istoricul nu este trimis modelului.
- Sursele includ numele documentului, pagina și fragmentul. Scorul de similaritate nu reprezintă o probabilitate de corectitudine. `MIN_SCORE` trebuie calibrat cu întrebări relevante și întrebări fără răspuns în corpus.
- Citările sunt verificate ca identificatori, nu ca adevăr al afirmațiilor. Modelul poate greși, poate cita greșit și poate fi influențat de documente malițioase, chiar cu instrucțiunile defensive incluse. Verifică sursele înainte de schimbări operaționale.
- SQLite păstrează textul extras, metadatele și embeddings în `data/knowledge.sqlite3`. Fișierele originale nu sunt arhivate. Ștergerea elimină documentul din indexul activ, nu și din backupurile existente sau garantat din spațiul liber SQLite.
- La schimbarea modelului de embeddings, șterge și reimportă documentele. La actualizarea modelului sub același tag, reindexează de asemenea; pentru reproducibilitate păstrează evidența digestului din `ollama list`.
- Căutarea exactă prin vectorii din SQLite este destinată unei biblioteci locale mici/medii. Pentru volume mari și acces concurent recomand migrare la PostgreSQL + pgvector. Această versiune simplifică operarea pe un singur calculator.

## Backup AWS S3, opțional

Implicit `S3_ENABLED=false`. Serverul web nu inițiază conexiuni AWS și nu oferă butoane de upload cloud. Doar comanda explicită de mai jos trimite o copie a bazei la S3: **textul documentelor și embeddings părăsesc calculatorul**. Modelele și întrebările nu sunt incluse.

1. Folosește un bucket privat, cu Block Public Access, Versioning și criptare la rest. Configurează lifecycle și retenția potrivite datelor tale. Aplicația nu creează sau modifică bucketul.
2. Preferă AWS CLI SSO / credențiale temporare: `aws sso login --profile personal`. SDK-ul folosește lanțul standard de credențiale; nu pune chei în cod.
3. Setează în `.env`:

```dotenv
S3_ENABLED=true
S3_BUCKET=numele-bucketului-tau
S3_PREFIX=devops-rag/backups/
AWS_PROFILE=personal
AWS_DEFAULT_REGION=eu-central-1
```

Upload manual, cu snapshot SQLite consistent și checksum SHA-256:

```powershell
.\.venv\Scripts\python.exe -m app.backup upload
```

Comanda afișează cheia completă a obiectului. Pentru restaurare, **oprește serverul**, setează `DATA_DIR=./data-restored` într-o locație nouă, apoi:

```powershell
.\.venv\Scripts\python.exe -m app.backup restore --key devops-rag/backups/CHEIA-AFISATA.sqlite3
```

Restaurarea refuză suprascrierea unei baze existente, verifică SHA-256, integritatea SQLite și structura de bază. Limita este 512 MiB. Checksumul detectează coruperea; nu autentifică un obiect modificat de cineva cu drepturi de scriere asupra bucketului. Nu restaura backupuri din surse neîncrezătoare. Pornește serverul cu noul `DATA_DIR` și același model embeddings. Backupurile nu includ modelele Ollama sau PDF-urile originale; arhivează-le separat dacă ai nevoie de recuperare completă.

Politică IAM minimă pentru prefix (înlocuiește numele bucketului):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:AbortMultipartUpload"],
    "Resource": "arn:aws:s3:::NUME-BUCKET/devops-rag/backups/*"
  }]
}
```

Nu sunt necesare drepturi de ștergere sau administrare a bucketului. Pentru SSE-KMS setează `S3_KMS_KEY_ID` și configurează separat politica KMS cu `kms:GenerateDataKey` și `kms:Decrypt`, limitate la cheia și rolul folosite. Snapshoturile sunt criptate server-side prin SSE-S3 implicit, sau SSE-KMS când cheia este configurată. Criptarea locală a discului se gestionează prin BitLocker și ACL Windows.

## Securitate și operare

Serverul este destinat unui singur utilizator și trebuie legat numai la `127.0.0.1`. Are validare Host, token pentru operații de scriere, fără CORS permisiv, CSP și afișare a textului fără HTML executabil. Acestea nu înlocuiesc autentificarea; orice proces local cu acces la port poate obține tokenul. Nu expune aplicația în LAN/Internet în această formă.

Pentru o versiune enterprise sunt necesare OIDC, autorizare la nivel de document înainte de retrieval, audit, limite globale de request, izolarea procesării PDF, evaluări RAG, dependențe blocate cu hashuri, SBOM și un proces documentat de vulnerabilități și actualizări. Cerințele sunt intervale de versiuni pentru dezvoltare; nu reprezintă un lockfile de producție. Aplicația nu constituie o certificare CRA.

Teste (fără GPU sau AWS, cu adaptoare simulate):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Verificare completă cu modelele reale (Ollama pornit, corpus temporar):

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_local
```

Documentație API: [Ollama embeddings](https://docs.ollama.com/api/embed), [Ollama chat](https://docs.ollama.com/api/chat), [Boto3 upload](https://docs.aws.amazon.com/boto3/latest/guide/s3-uploading-files.html).

## Import din docs/

Pune PDF, Markdown sau TXT in `docs/`, inclusiv subfoldere. Lista fara indexare sau conexiuni Ollama:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_docs --dry-run
```

Pentru import, porneste Ollama si opreste temporar serverul web pentru a evita importuri concurente intre procese:

```powershell
.\.venv\Scripts\python.exe -m scripts.import_docs
```

Alt director: `--path "C:/cale/documente"`. Limitele din `.env` se aplica si aici. Comanda afiseaza progresul, continua dupa erori si returneaza codul 1 daca un fisier esueaza. Fisierele ascunse, directoarele ascunse, linkurile simbolice si junction-urile din arbore sunt omise.

Duplicatele sunt omise dupa SHA-256. Fisierele modificate sunt documente noi; versiunea veche nu este stearsa automat. Sterge-o explicit din interfata daca nu mai trebuie folosita. Numele sursei este numele fisierului; foloseste nume distinctive pentru documente diferite cu acelasi nume din subfoldere. Nu exista monitorizare automata a folderului.

Originalele raman in `docs/`, excluse din Git. Dupa import reporneste serverul si reincarca pagina.
