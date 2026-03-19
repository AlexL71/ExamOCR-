import cv2
import numpy as np
from scipy.stats import linregress

def get_ranges(projection, min_width=5):
    if np.max(projection) == 0: return []
    threshold = np.max(projection) * 0.05
    active = np.where(projection > threshold)[0]
    if len(active) == 0: return []
    
    ranges = []
    start = active[0]
    prev = active[0]
    
    for i in active[1:]:
        if i > prev + 5: 
            if (prev - start) > min_width:
                ranges.append((start, prev))
            start = i
        prev = i
    if (prev - start) > min_width:
        ranges.append((start, prev))
    return ranges

def get_row_centers_robust(h_proj, height):
    row_ranges = get_ranges(h_proj, min_width=5)
    centers = [(r[0] + r[1]) // 2 for r in row_ranges]
    centers = [c for c in centers if c > height * 0.05 and c < height * 0.98]
    
    if len(centers) >= 5:
        indices = np.arange(len(centers))
        slope, intercept, _, _, _ = linregress(indices, centers)
        predicted_centers = [int(slope * i + intercept) for i in range(10)]
        half_h = int(slope * 0.35)
        return [(max(0, c - half_h), min(height, c + half_h)) for c in predicted_centers]
        
    if len(row_ranges) > 10: return row_ranges[-10:]
    return row_ranges[:10]

def get_char(col, row, is_id):
    if not is_id: return str(row)
    if col == 2: return "STVWXYZ"[row] if row < 7 else "?"
    if col == 3: return "ABCDEFGHJK"[row] if row < 10 else "?"
    if col == 4: return "LMNQRSTUVW"[row] if row < 10 else "?"
    return str(row)

def read_omr_smart(image, expected_cols, is_id=False):
    if image is None: return "ERROR", [], None
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, grid_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    h, w = grid_mask.shape

    r_channel = image[:, :, 2]
    _, pencil_mask = cv2.threshold(r_channel, 180, 255, cv2.THRESH_BINARY_INV)

    v_proj = np.sum(grid_mask, axis=0)
    col_ranges = get_ranges(v_proj, min_width=10)
    
    if len(col_ranges) > expected_cols:
         col_ranges = sorted(col_ranges, key=lambda x: x[1]-x[0], reverse=True)[:expected_cols]
         col_ranges.sort(key=lambda x: x[0])

    roi_rows = grid_mask[:, int(w*0.25):] 
    h_proj = np.sum(roi_rows, axis=1)
    row_ranges = get_row_centers_robust(h_proj, h)

    debug = image.copy()
    detected_options = []
    
    start_c = 2 if is_id else 0
    if is_id: detected_options.extend([['C'], ['A']])
    
    for logical_c in range(start_c, expected_cols):
        vis_idx = logical_c 
        
        if vis_idx >= len(col_ranges):
            detected_options.append(['?'])
            continue
            
        x1, x2 = col_ranges[vis_idx]
        candidates = []
        valid_rows = range(7) if (is_id and logical_c == 2) else range(10)
        
        for r_idx in valid_rows:
            if r_idx >= len(row_ranges): break
            y1, y2 = row_ranges[r_idx]
            
            h_cell = y2 - y1
            w_cell = x2 - x1
            my = int(h_cell * 0.2) 
            mx = int(w_cell * 0.2) 
            
            cell = pencil_mask[y1+my : y2-my, x1+mx : x2-mx]
            if cell.size == 0: continue
            
            fill = cv2.countNonZero(cell)
            ratio = fill / cell.size
            
            cv2.rectangle(debug, (x1, y1), (x2, y2), (200, 200, 200), 1)
            cv2.rectangle(debug, (x1+mx, y1+my), (x2-mx, y2-my), (255, 200, 150), 1)

            if ratio >= 0.05:
                is_doubtful = ratio < 0.12 
                candidates.append((r_idx, ratio, x1, y1, x2, y2, is_doubtful))

        col_chars = []
        if not candidates:
            col_chars.append('?')
        else:
            candidates.sort(key=lambda x: x[1], reverse=True)
            max_ratio = candidates[0][1]
            valid_cands = [c for c in candidates if c[1] > max_ratio * 0.60]
            
            if len(valid_cands) == 1:
                best = valid_cands[0]
                if best[6]: 
                    col_chars.append('!')
                    cv2.rectangle(debug, (best[2], best[3]), (best[4], best[5]), (0, 165, 255), 2)
                else:
                    val = get_char(logical_c, best[0], is_id)
                    col_chars.append(val)
                    cv2.rectangle(debug, (best[2], best[3]), (best[4], best[5]), (0, 255, 0), 2)
            else:
                col_chars.append('!')
                for c in valid_cands:
                    cv2.rectangle(debug, (c[2], c[3]), (c[4], c[5]), (0, 0, 255), 2)
        
        detected_options.append(col_chars)

    display_str = "".join([o[0] if len(o)==1 else "!" for o in detected_options])
    return display_str, detected_options, debug

def match_with_db_sqlite(id_str, dob_str, cursor):
    id_match, dob_match = False, False
    student_by_id, student_by_dob = None, None
    
    if '!' not in id_str and '?' not in id_str:
        cursor.execute("SELECT * FROM test_takers WHERE exam_id = ?", (id_str,))
        student_by_id = cursor.fetchone()
        if student_by_id:
            id_match = True
            
    if '!' not in dob_str and '?' not in dob_str:
        cursor.execute("SELECT * FROM test_takers WHERE birth_date = ? OR birth_date = ?", (dob_str, dob_str.lstrip('0')))
        student_by_dob = cursor.fetchone()
        if student_by_dob:
            dob_match = True

    candidate = student_by_id if student_by_id else student_by_dob
    if id_match and dob_match and student_by_id[0] != student_by_dob[0]:
        candidate = None
        
    return id_match, dob_match, candidate