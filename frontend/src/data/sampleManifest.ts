export interface SampleAsset {
  id: string;
  src: string;
}

export const SAMPLE_MANIFEST: SampleAsset[] = [
  { id: 'sample-1', src: '/samples/sample_01.jpg' },
  { id: 'sample-2', src: '/samples/sample_02.jpg' },
  { id: 'sample-3', src: '/samples/sample_03.jpg' },
  { id: 'sample-4', src: '/samples/sample_04.jpg' },
  { id: 'sample-5', src: '/samples/sample_05.jpg' },
  { id: 'sample-6', src: '/samples/sample_06.jpg' },
  { id: 'sample-7', src: '/samples/sample_07.jpg' },
  { id: 'sample-8', src: '/samples/sample_08.jpg' },
  { id: 'sample-9', src: '/samples/sample_09.jpg' },
];

/** Minimalist 1x1 JPEG byte array for synthetic fallback in offline/test environments. */
const FALLBACK_JPEG_BYTES = new Uint8Array([
  0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
  0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
  0x00, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01, 0x00, 0x01, 0x01, 0x01,
  0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00, 0x01, 0x05, 0x01, 0x01,
  0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0xFF,
  0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0x7F, 0x00, 0xFF, 0xD9
]);

/**
 * Fetch sample asset image and return a File object ready for upload.
 */
export async function getSampleFile(sample: SampleAsset): Promise<File> {
  const filename = `${sample.id}.jpg`;
  try {
    const res = await fetch(sample.src);
    if (res.ok) {
      const blob = await res.blob();
      return new File([blob], filename, { type: 'image/jpeg' });
    }
  } catch {
    // Silent fallback for test environments where static assets are not served via HTTP
  }

  const fallbackBlob = new Blob([FALLBACK_JPEG_BYTES], { type: 'image/jpeg' });
  return new File([fallbackBlob], filename, { type: 'image/jpeg' });
}
