import cv2, numpy as np, sys
sys.path.insert(0, 'backend')
from app.services.coordinate_normalizer import safer_annotation_masking, build_protected_geometry_mask

img = cv2.imread('samples/manual_qa/interface_b_original.jpg')
h, w, _ = img.shape
print(f'Image: {w}x{h}')

protected_mask, bbox = build_protected_geometry_mask(img)
print(f'Protected profile wall bbox: {bbox}')
print(f'Non-zero pixels in protected mask: {np.sum(protected_mask > 0)}')

crop_box = [22, 140, 955, 857]
annotation_regions = [
    [41, 290, 80, 396],
    [134, 275, 179, 392],
    [262, 831, 335, 874],
    [520, 847, 590, 891],
    [455, 467, 502, 590],
    [569, 391, 627, 477],
    [906, 469, 946, 513],
    [522, 50, 563, 67],
    [230, 48, 273, 65]
]

cleaned_bgr, raw_mask, final_crop, crop_rejected, meta = safer_annotation_masking(img, annotation_regions, crop_box)
print(f'Crop rejected: {crop_rejected}')
print(f'Final crop: {final_crop}')
print(f'Applied regions: {meta["applied_regions_count"]}')
print(f'Rejected regions: {meta["rejected_regions_count"]}')

for ar in meta['applied_regions']:
    print(f'  APPLIED: {ar["id"]} -> {ar["box_pixels"]}')
for rr in meta['rejected_regions']:
    print(f'  REJECTED: {rr["id"]} -> {rr.get("reason", "unknown")}')
