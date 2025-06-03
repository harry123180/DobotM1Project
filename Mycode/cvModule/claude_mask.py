import cv2
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

def detect_and_isolate_circles(image_path, output_dir, debug=False):
    """
    Detect circles in an image and isolate them with clean masks
    
    Args:
        image_path: Path to input image
        output_dir: Directory to save isolated circles
        debug: Whether to show debug visualization
    """
    # Read image
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"Cannot read image: {image_path}")
        return []
    
    # Create a copy for visualization
    vis_img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    
    # Pre-processing
    equalized = cv2.equalizeHist(img)
    blurred = cv2.GaussianBlur(equalized, (5, 5), 0)
    
    # Two-stage approach for circle detection
    # 1. First rough threshold to find potential regions
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # 2. Use HoughCircles for more precise circle detection
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=40,  # Minimum distance between circles
        param1=50,   # Upper threshold for Canny edge detector
        param2=30,   # Threshold for center detection
        minRadius=20,
        maxRadius=100
    )
    
    # Store results
    isolated_circles = []
    
    if circles is not None:
        circles = np.uint16(np.around(circles[0]))
        
        for i, (x, y, r) in enumerate(circles):
            # Create tight mask for this circle only
            mask = np.zeros_like(img)
            cv2.circle(mask, (x, y), r, 255, -1)
            
            # Calculate distance transform to help separate nearby circles
            dist_transform = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
            dist_transform = cv2.normalize(dist_transform, None, 0, 1.0, cv2.NORM_MINMAX)
            
            # Use watershed to refine circle boundaries
            _, markers = cv2.connectedComponents(np.uint8(dist_transform > 0.7))
            
            # Create final mask
            final_mask = np.zeros_like(img)
            final_mask[markers == 1] = 255
            
            # Apply mask to original image
            circle_img = img.copy()
            circle_img[final_mask == 0] = 255  # Set background to white
            
            # Crop to bounding box with padding
            padding = 5
            x1 = max(0, x - r - padding)
            y1 = max(0, y - r - padding)
            x2 = min(img.shape[1], x + r + padding)
            y2 = min(img.shape[0], y + r + padding)
            cropped = circle_img[y1:y2, x1:x2]
            
            # Save the isolated circle
            if output_dir:
                output_path = output_dir / f"{image_path.stem}_circle_{i+1}.png"
                cv2.imwrite(str(output_path), cropped)
            
            # Store result
            isolated_circles.append({
                "center": (x, y),
                "radius": r,
                "cropped_image": cropped,
                "path": str(output_path) if output_dir else None
            })
            
            # Draw on visualization image
            cv2.circle(vis_img, (x, y), r, (0, 255, 0), 2)
            cv2.circle(vis_img, (x, y), 2, (0, 0, 255), 3)
            cv2.putText(vis_img, str(i+1), (x-10, y-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
    
    if debug and output_dir:
        cv2.imwrite(str(output_dir / f"{image_path.stem}_detected.png"), vis_img)
    
    return isolated_circles

def adaptive_circle_isolation(img_path, output_dir):
    """Enhanced method using adaptive thresholding and watershed"""
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []
    
    # Enhance contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(img)
    
    # Remove noise
    denoised = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)
    
    # Adaptive thresholding
    binary = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY_INV, 11, 2)
    
    # Morphological operations to separate touching circles
    kernel = np.ones((3,3), np.uint8)
    opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
    
    # Distance transform
    dist = cv2.distanceTransform(opening, cv2.DIST_L2, 5)
    
    # Find peaks in distance transform (circle centers)
    _, dist_thresh = cv2.threshold(dist, 0.5*dist.max(), 255, 0)
    dist_thresh = np.uint8(dist_thresh)
    
    # Find markers for watershed
    _, markers = cv2.connectedComponents(dist_thresh)
    
    # Apply watershed
    markers = markers + 1
    markers[binary == 0] = 0
    
    # Convert to color for watershed
    img_color = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cv2.watershed(img_color, markers)
    
    # Process each detected circle
    isolated_circles = []
    for marker_idx in range(2, markers.max() + 1):
        # Extract this circle
        circle_mask = np.zeros_like(img, dtype=np.uint8)
        circle_mask[markers == marker_idx] = 255
        
        # Find contour to get center and radius
        contours, _ = cv2.findContours(circle_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
            
        # Get circle properties
        contour = max(contours, key=cv2.contourArea)
        (x, y), radius = cv2.minEnclosingCircle(contour)
        center = (int(x), int(y))
        radius = int(radius)
        
        # Check if it's circular enough (filter non-circular shapes)
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if circularity < 0.7:  # Filter non-circular objects
            continue
        
        # Create a clean circular mask
        clean_mask = np.zeros_like(img, dtype=np.uint8)
        cv2.circle(clean_mask, center, radius, 255, -1)
        
        # Extract original image with clean circular mask
        circle_img = img.copy()
        circle_img[clean_mask == 0] = 255  # White background
        
        # Crop to bounding box
        padding = 5
        x1 = max(0, int(x) - radius - padding)
        y1 = max(0, int(y) - radius - padding)
        x2 = min(img.shape[1], int(x) + radius + padding)
        y2 = min(img.shape[0], int(y) + radius + padding)
        cropped = circle_img[y1:y2, x1:x2]
        
        # Save the isolated circle
        if output_dir:
            output_path = output_dir / f"{img_path.stem}_adaptive_circle_{marker_idx-1}.png"
            cv2.imwrite(str(output_path), cropped)
        
        isolated_circles.append({
            "center": center,
            "radius": radius,
            "circularity": circularity,
            "cropped_image": cropped,
            "path": str(output_path) if output_dir else None
        })
    
    return isolated_circles


# Example usage
if __name__ == "__main__":
    input_path = Path("D:/AWORKSPACE/Github/DobotM1Project/parameter/CASE/BD-00009260-CASE-back/1.bmp")
    output_dir = Path("D:/AWORKSPACE/Github/DobotM1Project/Mycode/output")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Method 1: HoughCircles based
    circles1 = detect_and_isolate_circles(input_path, output_dir, debug=True)
    print(f"Detected {len(circles1)} circles with method 1")
    
    # Method 2: Watershed based
    circles2 = adaptive_circle_isolation(input_path, output_dir)
    print(f"Detected {len(circles2)} circles with method 2")