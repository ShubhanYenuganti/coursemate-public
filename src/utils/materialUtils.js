/**
 * Returns the best URL to open a material in its source system.
 * - gdrive: outsourced_url → drive fallback → S3 download
 * - notion / other integrations: outsourced_url → S3 download
 * - upload: S3 download_url
 */
export function getMaterialUrl(material) {
  const driveFallbackUrl = material?.external_id
    ? `https://drive.google.com/file/d/${material.external_id}/view`
    : null;
  return material?.source_type === 'gdrive'
    ? material?.outsourced_url || driveFallbackUrl || material?.download_url
    : material?.source_type !== 'upload' && material?.outsourced_url
      ? material.outsourced_url
      : material?.download_url;
}
