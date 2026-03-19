import cv2
import numpy as np
import fitz

class ExamAligner:
    def __init__(self, target_long=2828, target_short=2000):
        self.long_edge = target_long
        self.short_edge = target_short

    def find_corner_marker(self, img, offset_x, offset_y, is_right, is_bottom):
        if img is None or img.size == 0: 
            return (offset_x, offset_y)
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        tx = img.shape[1] if is_right else 0
        ty = img.shape[0] if is_bottom else 0
        best_pt, min_d = None, float('inf')

        for c in cnts:
            area = cv2.contourArea(c)
            if 50 < area < 5000:
                x, y, w, h = cv2.boundingRect(c)
                if 0.7 <= w / float(h) <= 1.3:
                    cx, cy = x + w // 2, y + h // 2
                    d = (cx - tx)**2 + (cy - ty)**2
                    if d < min_d:
                        min_d, best_pt = d, (cx + offset_x, cy + offset_y)
                        
        return best_pt if best_pt else (tx + offset_x, ty + offset_y)

    def align_image(self, img):
        if img is None or img.size == 0: 
            return None
            
        h, w = img.shape[:2]
        cx, cy = w // 2, h // 2
        
        tl = self.find_corner_marker(img[0:cy, 0:cx], 0, 0, False, False)
        tr = self.find_corner_marker(img[0:cy, cx:w], cx, 0, True, False)
        br = self.find_corner_marker(img[cy:h, cx:w], cx, cy, True, True)
        bl = self.find_corner_marker(img[cy:h, 0:cx], 0, cy, False, True)
        
        dist_top = np.linalg.norm(np.array(tl) - np.array(tr))
        dist_left = np.linalg.norm(np.array(tl) - np.array(bl))
        
        is_landscape = dist_top > dist_left
        temp_w = self.long_edge if is_landscape else self.short_edge
        temp_h = self.short_edge if is_landscape else self.long_edge

        src = np.array([tl, tr, br, bl], dtype="float32")
        dst = np.array([[0, 0], [temp_w, 0], [temp_w, temp_h], [0, temp_h]], dtype="float32")
        warped = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (temp_w, temp_h))
        
        if is_landscape:
            warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
            target_h = self.long_edge
        else:
            target_h = temp_h
            
        hsv = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)
        red_mask = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([10, 255, 255])) + \
                   cv2.inRange(hsv, np.array([170, 50, 50]), np.array([180, 255, 255]))
        
        coords = cv2.findNonZero(red_mask)
        if coords is not None:
            _, gy, _, gh = cv2.boundingRect(coords)
            if gy < (target_h - (gy + gh)):
                warped = cv2.rotate(warped, cv2.ROTATE_180)

        return warped

def process_pdf_pages(pdf_path, aligner, dpi=300):
    try:
        doc = fitz.open(pdf_path)
        aligned_pages = []
        
        for page_num in range(len(doc)):
            pix = doc.load_page(page_num).get_pixmap(dpi=dpi)
            if pix.colorspace.n != 3 or pix.alpha:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            aligned = aligner.align_image(img)
            if aligned is not None:
                h, w = aligned.shape[:2]
                gray = cv2.cvtColor(aligned[0:int(h * 0.15), 0:w], cv2.COLOR_BGR2GRAY)
                _, bin_img = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
                density = cv2.countNonZero(bin_img)
                aligned_pages.append({'img': aligned, 'density': density})
                
        aligned_pages.sort(key=lambda x: x['density'], reverse=True)
        return [page['img'] for page in aligned_pages]
        
    except Exception:
        return []