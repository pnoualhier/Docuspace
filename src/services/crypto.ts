/**
 * Client-side cryptographic helper & MIME validation
 */

export async function calculateSHA256(file: File | Blob): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

export function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return '0 o';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['o', 'Ko', 'Mo', 'Go', 'To'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

export function getFileCategory(mimeType: string, extension: string): 'pdf' | 'image' | 'word' | 'excel' | 'archive' | 'code' | 'other' {
  const ext = extension.toLowerCase();
  if (mimeType.includes('pdf') || ext === 'pdf') return 'pdf';
  if (mimeType.startsWith('image/') || ['png', 'jpg', 'jpeg', 'webp', 'gif', 'svg'].includes(ext)) return 'image';
  if (mimeType.includes('word') || ['doc', 'docx', 'odt'].includes(ext)) return 'word';
  if (mimeType.includes('sheet') || mimeType.includes('excel') || ['xls', 'xlsx', 'csv'].includes(ext)) return 'excel';
  if (['zip', 'tar', 'gz', '7z', 'rar'].includes(ext)) return 'archive';
  if (['json', 'xml', 'md', 'txt', 'py', 'ts', 'js', 'html', 'css', 'sql'].includes(ext)) return 'code';
  return 'other';
}

export function generateStorageKey(tenantId: string, extension: string): string {
  const randomUuid = crypto.randomUUID();
  const cleanExt = extension.replace(/^\./, '');
  return `tenants/${tenantId}/${randomUuid}.${cleanExt}`;
}
