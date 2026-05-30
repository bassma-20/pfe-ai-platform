import axios from 'axios';

const BASE = '/api/migration';

// ─── 1. Upload fichier Java ou Python ────────────────────────────────────────
export async function uploadFile(file) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await axios.post(`${BASE}/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data; // { message, filename, language, size_bytes }
}

// Alias rétro-compatible
export const uploadJavaFile = uploadFile;

// ─── 2. Lancer la migration ───────────────────────────────────────────────────
// target_version : Java → "8"|"11"|"17"|"21"  |  Python → "3.8"|"3.10"|"3.12"
export async function migrateFile(filename, targetVersion = '17') {
  const { data } = await axios.post(`${BASE}/migrate`, null, {
    params: { filename, target_version: targetVersion },
  });
  return data;
}

// ─── 3. Télécharger le fichier migré ─────────────────────────────────────────
export function getDownloadUrl(filename) {
  const isPython = filename.endsWith('.py');
  const stem = filename
    .replace(/_migrated\.(java|py)$/, '')
    .replace(/\.(java|py)$/, '');
  const ext = isPython ? '.py' : '.java';
  return `${BASE}/download/${stem}_migrated${ext}`;
}

export async function downloadMigratedFile(filename) {
  const url = getDownloadUrl(filename);
  const { data } = await axios.get(url, { responseType: 'blob' });
  const isPython = filename.endsWith('.py');
  const stem = filename.replace(/\.(java|py)$/, '');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(data);
  link.download = `${stem}_migrated${isPython ? '.py' : '.java'}`;
  link.click();
  URL.revokeObjectURL(link.href);
}

// ─── 4. Migration agentique — boucle de réflexion (Idée 1) ──────────────────
export async function migrateFileAgent(filename, targetVersion = '17', maxIterations = 3) {
  const { data } = await axios.post(`${BASE}/migrate-agent`, null, {
    params: { filename, target_version: targetVersion, max_iterations: maxIterations },
  });
  return data;
}

// ─── 5. Migration multi-agents — boucle de réparation progressive ────────────
// Optimisé : Vérificateur LLM ne tourne QU'UNE FOIS à la fin.
// Entre les tentatives : analyseur statique gratuit (pas de LLM).
// max_rework=3 → 4 tentatives max (Analyste + 4×Migrateur + Vérificateur = 6 LLM calls max)
// Arrêt anticipé dès que 0 problème restant ou stagnation.
export async function migrateFileMultiAgent(filename, targetVersion = '17', maxRework = 3) {
  const { data } = await axios.post(`${BASE}/migrate-multi-agent`, null, {
    params: { filename, target_version: targetVersion, max_rework: maxRework },
    timeout: 420000,  // 7 minutes — jusqu'à 4 passes de migration
  });
  return data;
}

// ─── 6. Exécuter le code migré ───────────────────────────────────────────────
export async function executeCode(code, language) {
  const { data } = await axios.post(`${BASE}/execute`, { code, language });
  return data; // { stdout, stderr, exit_code, success }
}

// ─── 6b. Générer un main() via LLM puis exécuter ─────────────────────────────
export async function generateAndExecute(code, language) {
  const { data } = await axios.post(`${BASE}/generate-and-execute`, { code, language });
  return data; // { generated_code, stdout, stderr, exit_code, success }
}

// ─── 7. Historique des fichiers migrés ───────────────────────────────────────
export async function getMigrationHistory() {
  const { data } = await axios.get(`${BASE}/history`);
  return data; // { count, files: [{ filename, language, size_bytes, download_url }] }
}
