"""
GPS Extraction Module - Universal Compatibility Engine
Handles GPS extraction from images with maximum robustness.
Supports all major phone manufacturers and EXIF formats.
"""

import logging
from typing import Tuple, Optional, Union
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS, IFD
import math

# Configure module-specific logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def dms_to_decimal(
    dms_data: Union[tuple, list], 
    ref: str
) -> Optional[float]:
    """
    Convert DMS (Degrees, Minutes, Seconds) to decimal degrees.
    
    Critical robustness features:
    - Handles IFDRational objects from Pillow
    - Comprehensive error handling with ZeroDivisionError protection
    - Never returns 0.0 on error (returns None instead)
    - Validates coordinate ranges
    
    Args:
        dms_data: Tuple/list of three values (degrees, minutes, seconds)
        ref: Reference direction ('N', 'S', 'E', 'W')
    
    Returns:
        Decimal degrees as float, or None if conversion fails
    """
    try:
        # Input validation
        if not dms_data or len(dms_data) != 3:
            logger.warning(f"Invalid DMS data structure: {dms_data}")
            return None
            
        if ref not in ['N', 'S', 'E', 'W']:
            logger.warning(f"Invalid reference direction: {ref}")
            return None
        
        # Extract and convert each component with ZeroDivisionError protection
        components = []
        component_names = ['degrees', 'minutes', 'seconds']
        
        for i, (value, name) in enumerate(zip(dms_data, component_names)):
            try:
                # Handle IFDRational objects (Pillow format)
                if hasattr(value, 'numerator') and hasattr(value, 'denominator'):
                    if value.denominator == 0:
                        logger.error(f"Zero denominator in {name}")
                        return None
                    components.append(value.numerator / value.denominator)
                    
                # Handle tuple format (alternative EXIF format)
                elif isinstance(value, (tuple, list)) and len(value) == 2:
                    if value[1] == 0:
                        logger.error(f"Zero denominator in {name} tuple")
                        return None
                    components.append(value[0] / value[1])
                    
                # Handle direct numeric values
                elif isinstance(value, (int, float)):
                    components.append(float(value))
                    
                else:
                    logger.error(f"Unknown format for {name}: {type(value)}")
                    return None
                    
            except ZeroDivisionError:
                logger.error(f"Division by zero in {name} component")
                return None
            except (TypeError, AttributeError) as e:
                logger.error(f"Error processing {name}: {e}")
                return None
        
        degrees, minutes, seconds = components
        
        # Validate component ranges
        if not (0 <= degrees <= 180):
            logger.warning(f"Invalid degrees value: {degrees}")
            return None
        if not (0 <= minutes < 60):
            logger.warning(f"Invalid minutes value: {minutes}")
            return None
        if not (0 <= seconds < 60):
            logger.warning(f"Invalid seconds value: {seconds}")
            return None
        
        # Calculate decimal degrees
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        
        # Apply reference direction
        if ref in ['S', 'W']:
            decimal = -decimal
        
        # Final validation
        if ref in ['N', 'S'] and not (-90 <= decimal <= 90):
            logger.warning(f"Latitude {decimal} out of valid range")
            return None
        if ref in ['E', 'W'] and not (-180 <= decimal <= 180):
            logger.warning(f"Longitude {decimal} out of valid range")
            return None
        
        # Null Island detection (0.0, 0.0 is suspicious)
        if abs(decimal) < 0.0001:  # Near zero
            logger.warning(f"Suspicious near-zero coordinate: {decimal}")
            # Don't immediately reject, but log for review
        
        logger.debug(f"Successfully converted DMS to decimal: {decimal}")
        return decimal
        
    except Exception as e:
        logger.error(f"Unexpected error in dms_to_decimal: {e}")
        return None


def extract_gps_with_exifread(image_path: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Alternative GPS extraction using ExifRead library.
    Provides additional compatibility for complex EXIF structures.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Tuple of (latitude, longitude) or (None, None) if extraction fails
    """
    try:
        import exifread
        
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
        
        # Check for GPS data presence
        gps_latitude = tags.get('GPS GPSLatitude')
        gps_latitude_ref = tags.get('GPS GPSLatitudeRef')
        gps_longitude = tags.get('GPS GPSLongitude')
        gps_longitude_ref = tags.get('GPS GPSLongitudeRef')
        
        if not all([gps_latitude, gps_latitude_ref, gps_longitude, gps_longitude_ref]):
            return (None, None)
        
        # Convert ExifRead format to decimal
        def exifread_to_decimal(values, ref):
            d = float(values[0].num) / float(values[0].den)
            m = float(values[1].num) / float(values[1].den)
            s = float(values[2].num) / float(values[2].den)
            
            decimal = d + (m / 60.0) + (s / 3600.0)
            if ref in ['S', 'W']:
                decimal = -decimal
            return decimal
        
        lat = exifread_to_decimal(gps_latitude.values, str(gps_latitude_ref.values))
        lon = exifread_to_decimal(gps_longitude.values, str(gps_longitude_ref.values))
        
        # Validate ranges
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return (None, None)
            
        return (lat, lon)
        
    except ImportError:
        logger.debug("ExifRead not available, skipping alternative method")
        return (None, None)
    except Exception as e:
        logger.error(f"ExifRead extraction failed: {e}")
        return (None, None)


def get_lat_lon(image: Image.Image) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract GPS coordinates from image with universal compatibility.
    
    Features:
    - Multiple extraction methods for maximum compatibility
    - Comprehensive error handling
    - Support for all major phone manufacturers
    - Never returns invalid coordinates
    
    Args:
        image: PIL Image object
        
    Returns:
        Tuple of (latitude, longitude) as floats, or (None, None) if extraction fails
    """
    try:
        # Method 1: Modern Pillow approach (most compatible)
        exif = image.getexif()
        
        if not exif:
            logger.warning("No EXIF data found in image")
            return (None, None)
        
        # Try to get GPS IFD
        gps_ifd = {}
        
        # Method 1a: Direct GPS IFD access
        try:
            gps_ifd = exif.get_ifd(IFD.GPSInfo)
        except Exception as e:
            logger.debug(f"Direct IFD access failed: {e}")
            
            # Method 1b: Manual GPS tag extraction
            for tag, value in exif.items():
                if tag in GPSTAGS:
                    gps_ifd[GPSTAGS[tag]] = value
        
        # Check for required GPS tags
        required_tags = ['GPSLatitude', 'GPSLatitudeRef', 'GPSLongitude', 'GPSLongitudeRef']
        
        for tag in required_tags:
            if tag not in gps_ifd:
                logger.warning(f"Missing required GPS tag: {tag}")
                
                # Method 2: Try alternative extraction with ExifRead
                if hasattr(image, 'filename'):
                    logger.info("Attempting ExifRead extraction...")
                    lat, lon = extract_gps_with_exifread(image.filename)
                    if lat is not None and lon is not None:
                        return (lat, lon)
                
                return (None, None)
        
        # Extract GPS data
        lat_data = gps_ifd['GPSLatitude']
        lat_ref = gps_ifd['GPSLatitudeRef']
        lon_data = gps_ifd['GPSLongitude']
        lon_ref = gps_ifd['GPSLongitudeRef']
        
        # Convert to decimal degrees
        latitude = dms_to_decimal(lat_data, lat_ref)
        longitude = dms_to_decimal(lon_data, lon_ref)
        
        # Critical validation
        if latitude is None or longitude is None:
            logger.warning("Failed to convert GPS coordinates to decimal")
            return (None, None)
        
        # Null Island detection
        if latitude == 0.0 and longitude == 0.0:
            logger.error("Null Island coordinates detected (0.0, 0.0) - likely corrupted data")
            return (None, None)
        
        # Final range validation
        if not (-90 <= latitude <= 90):
            logger.error(f"Invalid latitude: {latitude}")
            return (None, None)
        
        if not (-180 <= longitude <= 180):
            logger.error(f"Invalid longitude: {longitude}")
            return (None, None)
        
        logger.info(f"Successfully extracted coordinates: {latitude}, {longitude}")
        return (latitude, longitude)
        
    except Exception as e:
        logger.error(f"Unexpected error in get_lat_lon: {e}")
        return (None, None)


def validate_image_file(filename: str) -> bool:
    """
    Validate image file extension for security.
    
    Args:
        filename: Name of the uploaded file
        
    Returns:
        True if file extension is allowed, False otherwise
    """
    if not filename:
        return False
    
    allowed = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'tif', 'webp'}
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    return ext in allowed