# DocuSpace — Politique de Sécurité

## 1. Mots de Passe & Authentification
- Hachage cryptographique via **Argon2id** (memory_cost: 64 Mo, time_cost: 3, parallelism: 4).
- Jetons JWT signés (HMAC SHA-256) avec durée de vie courte (30 min) et rotation de jeton de rafraîchissement.
- Cookies **HttpOnly**, **SameSite=Lax/Strict** et **Secure** (activé sous HTTPS).
- Limitation des tentatives de connexion (`limit_req_zone` Nginx à 3 requêtes/seconde sur `/api/v1/auth/login`).

## 2. Sécurité du Stockage & Traitement des Fichiers
- **Clé opaque** : Les fichiers ne sont JAMAIS stockés sous leur nom original. Une clé UUID opaque `tenants/<tenant_id>/<doc_uuid>` est utilisée.
- **Vérification Magique MIME** : L'extension est décorrélée du type réel, vérifié via `libmagic` sur les premiers octets.
- **Fail-Closed Antivirus** : Tout fichier importé transite par ClamAV. En cas de suspicion ou d'indisponibilité du service antivirus, le fichier reste en statut `PENDING_SCAN` ou `REJECTED` et n'est jamais distribué aux clients.
- **Contenus Actifs (SVG, HTML)** : Servis avec l'en-tête `Content-Disposition: attachment` ou isolés pour empêcher toute exécution XSS sur l'origine principale.
- **SHA-256** : Calcul systématique de l'empreinte pour détection d'intégrité et de doublons.

## 3. Quotas Transactionnels
- Réservation de quota atomique avant le streaming d'upload.
- Libération en cas d'échec ou d'annulation.
- Verrou pessimiste en base pour empêcher le dépassement de quota lors d'uploads concurrents.
