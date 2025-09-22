
import os
import sys
import logging
import tempfile
import traceback
import json
from pathlib import Path
from datetime import datetime
from io import BytesIO
import base64

# Third-Party Imports
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import piexif


try:
    from dotenv import load_dotenv
    env_mode = os.environ.get('FLASK_ENV', 'development')
    env_file = Path(__file__).parent / f'.env.{env_mode}'
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✓ Loaded environment from {env_file}")
    else:
        load_dotenv()
        print("✓ Loaded default .env file")
except ImportError:
    print("⚠ python-dotenv not installed. Using system environment variables.")


logging.basicConfig(
    level=logging.DEBUG if os.environ.get('FLASK_DEBUG', 'False').lower() == 'true' else logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('geophoto.log', mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class ApplicationConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-please-change-in-production')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'tif', 'webp', 'heic', 'heif'}
    SESSION_COOKIE_SECURE = FLASK_ENV == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    @classmethod
    def init_app(cls, app):
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        for key in dir(cls):
            if key.isupper():
                app.config[key] = getattr(cls, key)
        logger.info(f"Application configured for {cls.FLASK_ENV} environment")


class EnhancedExifExtractor:
    """
    Enhanced extractor for complete EXIF data including GPS with editing capabilities.
    """
    
    @staticmethod
    def validate_file(filename):
        if not filename or '.' not in filename:
            return False
        ext = filename.rsplit('.', 1)[1].lower()
        return ext in ApplicationConfig.ALLOWED_EXTENSIONS
    
    @staticmethod
    def dms_to_decimal(dms_data, ref):
        """Convert DMS to decimal degrees with enhanced format support."""
        try:
            logger.debug(f"Converting DMS data: {dms_data}, ref: {ref}, type: {type(dms_data)}")

            
            if isinstance(ref, bytes):
                ref = ref.decode('utf-8').strip()
            
            if not dms_data:
                logger.warning("DMS data is None or empty")
                return None
                
            if ref not in ['N', 'S', 'E', 'W']:
                logger.warning(f"Invalid reference direction: {ref}")
                return None

            
            if isinstance(dms_data, (tuple, list)) and len(dms_data) == 3:
 
                try:
                    
                    if all(isinstance(x, (int, float)) for x in dms_data):
                        degrees = float(dms_data[0])
                        minutes = float(dms_data[1])
                        seconds = float(dms_data[2])
                        
                        logger.debug(f"Direct tuple conversion: d={degrees}, m={minutes}, s={seconds}")
                    
                        
                        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
                        
                   
                        if ref in ['S', 'W']:
                            decimal = -decimal
                        
                        logger.info(f"Successfully converted: {dms_data} -> {decimal}")
                        return decimal
                        
                except Exception as e:
                    logger.debug(f"Failed direct tuple conversion: {e}")
          
            
            components = []
            for i, value in enumerate(dms_data):
                try:
                    if isinstance(value, (int, float)):
                        components.append(float(value))
                    elif hasattr(value, 'numerator') and hasattr(value, 'denominator'):
                        if value.denominator == 0:
                            return None
                        components.append(value.numerator / value.denominator)
                    elif isinstance(value, (tuple, list)) and len(value) == 2:
                        if value[1] == 0:
                            return None
                        components.append(value[0] / value[1])
                    else:
                        logger.warning(f"Unknown value type at index {i}: {type(value)}")
                        return None
                except Exception as e:
                    logger.warning(f"Error processing component {i}: {e}")
                    return None
            
            if len(components) != 3:
                logger.warning(f"Expected 3 components, got {len(components)}")
                return None
            
            degrees, minutes, seconds = components
            decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
            
            if ref in ['S', 'W']:
                decimal = -decimal
          
            
            if ref in ['N', 'S'] and not (-90 <= decimal <= 90):
                logger.warning(f"Latitude {decimal} out of valid range")
                return None
            if ref in ['E', 'W'] and not (-180 <= decimal <= 180):
                logger.warning(f"Longitude {decimal} out of valid range")
                return None
            
            return decimal
            
        except Exception as e:
            logger.error(f"DMS conversion error: {e}")
            return None
    @staticmethod
    def decimal_to_dms(decimal, is_latitude):
        """Convert decimal degrees to DMS format for EXIF."""
        abs_decimal = abs(decimal)
        degrees = int(abs_decimal)
        minutes_decimal = (abs_decimal - degrees) * 60
        minutes = int(minutes_decimal)
        seconds = (minutes_decimal - minutes) * 60
      
        
        degrees_rational = (degrees, 1)
        minutes_rational = (minutes, 1)
        seconds_rational = (int(seconds * 10000), 10000)
        
        if is_latitude:
            ref = 'N' if decimal >= 0 else 'S'
        else:
            ref = 'E' if decimal >= 0 else 'W'
        
        return [degrees_rational, minutes_rational, seconds_rational], ref
    
    @staticmethod
    def extract_all_exif(image_path):
        """Extract complete EXIF data from image."""
        exif_data = {
            'gps': {},
            'camera': {},
            'image': {},
            'datetime': {},
            'other': {}
        }
        
        try:
            with Image.open(image_path) as img:
                # Get basic image info
                exif_data['image']['width'] = img.width
                exif_data['image']['height'] = img.height
                exif_data['image']['format'] = img.format
                exif_data['image']['mode'] = img.mode
                
                # Get file size
                exif_data['image']['file_size'] = os.path.getsize(image_path)
                
                exif = img.getexif()
                if not exif:
                    return exif_data
                
                # Process standard EXIF tags
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    
                    # Skip GPS IFD (processed separately)
                    if tag == 'GPSInfo':
                        continue
                    
                    # Categorize EXIF data
                    if tag in ['Make', 'Model', 'LensMake', 'LensModel']:
                        exif_data['camera'][tag] = str(value)
                    elif tag in ['ISOSpeedRatings', 'ISO']:
                        exif_data['camera']['ISO'] = value
                    elif tag in ['FNumber', 'ApertureValue']:
                        if hasattr(value, 'numerator'):
                            exif_data['camera']['Aperture'] = f"f/{value.numerator/value.denominator:.1f}"
                        else:
                            exif_data['camera']['Aperture'] = f"f/{value}"
                    elif tag in ['ExposureTime', 'ShutterSpeedValue']:
                        if hasattr(value, 'numerator'):
                            if value.numerator == 1:
                                exif_data['camera']['ShutterSpeed'] = f"1/{value.denominator}s"
                            else:
                                exif_data['camera']['ShutterSpeed'] = f"{value.numerator}/{value.denominator}s"
                        else:
                            exif_data['camera']['ShutterSpeed'] = str(value)
                    elif tag == 'FocalLength':
                        if hasattr(value, 'numerator'):
                            exif_data['camera']['FocalLength'] = f"{value.numerator/value.denominator:.1f}mm"
                        else:
                            exif_data['camera']['FocalLength'] = f"{value}mm"
                    elif tag == 'Flash':
                        flash_modes = {0: 'No Flash', 1: 'Fired', 5: 'Fired, No Return', 7: 'Fired, Return'}
                        exif_data['camera']['Flash'] = flash_modes.get(value, f'Mode {value}')
                    elif tag == 'WhiteBalance':
                        wb_modes = {0: 'Auto', 1: 'Manual'}
                        exif_data['camera']['WhiteBalance'] = wb_modes.get(value, str(value))
                    elif tag == 'ExposureMode':
                        exp_modes = {0: 'Auto', 1: 'Manual', 2: 'Auto Bracket'}
                        exif_data['camera']['ExposureMode'] = exp_modes.get(value, str(value))
                    elif tag in ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']:
                        exif_data['datetime'][tag] = str(value)
                    elif tag == 'Orientation':
                        orientations = {
                            1: 'Normal', 2: 'Mirrored', 3: 'Rotated 180°',
                            4: 'Mirrored & Rotated 180°', 5: 'Mirrored & Rotated 270°',
                            6: 'Rotated 90°', 7: 'Mirrored & Rotated 90°', 8: 'Rotated 270°'
                        }
                        exif_data['image']['Orientation'] = orientations.get(value, str(value))
                    elif tag == 'Software':
                        exif_data['other']['Software'] = str(value)
                    else:
                        # Store other tags
                        if isinstance(value, bytes):
                            try:
                                exif_data['other'][tag] = value.decode('utf-8', errors='ignore')
                            except:
                                exif_data['other'][tag] = str(value)
                        else:
                            exif_data['other'][tag] = str(value)
                
                # Extract GPS data with enhanced parsing
                gps_ifd = {}
                try:
                    from PIL.ExifTags import IFD
                    gps_ifd = exif.get_ifd(IFD.GPSInfo)
                    logger.debug(f"GPS IFD extracted: {gps_ifd}")
                except Exception as e:
                    logger.warning(f"Failed to get GPS IFD: {e}")
                    # Fallback: manually extract GPS tags
                    for tag, value in exif.items():
                        if tag in GPSTAGS:
                            gps_ifd[GPSTAGS[tag]] = value
                    logger.debug(f"GPS tags extracted manually: {gps_ifd}")
                
                if gps_ifd:
                    logger.debug(f"Processing GPS data: {gps_ifd}")
                    
                    # Initialize coordinates
                    lat = None
                    lon = None
       
                    
                    if 1 in gps_ifd and 2 in gps_ifd and 3 in gps_ifd and 4 in gps_ifd:
                        try:
                            logger.debug("Found indexed GPS format")
                            lat_ref = gps_ifd[1]
                            lat_coords = gps_ifd[2]
                            lon_ref = gps_ifd[3]
                            lon_coords = gps_ifd[4]
      
                            
                            if isinstance(lat_ref, bytes):
                                lat_ref = lat_ref.decode('utf-8').strip()
                            if isinstance(lon_ref, bytes):
                                lon_ref = lon_ref.decode('utf-8').strip()
                            
                            logger.debug(f"Indexed format - Lat: {lat_coords} {lat_ref}, Lon: {lon_coords} {lon_ref}")
      
                            
                            lat = EnhancedExifExtractor.dms_to_decimal(lat_coords, lat_ref)
                            lon = EnhancedExifExtractor.dms_to_decimal(lon_coords, lon_ref)
                            
                            logger.info(f"Extracted from indexed format: lat={lat}, lon={lon}")
                            
                        except Exception as e:
                            logger.debug(f"Failed to extract from indexed format: {e}")
      
                    
                    if (lat is None or lon is None) and all(k in gps_ifd for k in ['GPSLatitude', 'GPSLatitudeRef', 'GPSLongitude', 'GPSLongitudeRef']):
                        try:
                            logger.debug("Attempting standard GPS extraction")
                            
                            lat_data = gps_ifd['GPSLatitude']
                            lat_ref = gps_ifd['GPSLatitudeRef']
                            lon_data = gps_ifd['GPSLongitude']
                            lon_ref = gps_ifd['GPSLongitudeRef']
     
                            
                            if isinstance(lat_ref, bytes):
                                lat_ref = lat_ref.decode('utf-8').strip()
                            if isinstance(lon_ref, bytes):
                                lon_ref = lon_ref.decode('utf-8').strip()
                            
                            lat = EnhancedExifExtractor.dms_to_decimal(lat_data, lat_ref)
                            lon = EnhancedExifExtractor.dms_to_decimal(lon_data, lon_ref)
                            
                            logger.info(f"Extracted from standard format: lat={lat}, lon={lon}")
                            
                        except Exception as e:
                            logger.debug(f"Failed standard extraction: {e}")
     
                    
     
                    if lat is not None and lon is not None:
     
                        if -90 <= lat <= 90 and -180 <= lon <= 180:
                            exif_data['gps']['latitude'] = lat
                            exif_data['gps']['longitude'] = lon
                            logger.info(f"GPS coordinates successfully stored: {lat}, {lon}")
                        else:
                            logger.warning(f"GPS coordinates out of range: lat={lat}, lon={lon}")
                    else:
                        logger.warning("Failed to extract GPS coordinates")
     
                        exif_data['gps']['debug_raw_data'] = str(gps_ifd)
                        logger.debug(f"Raw GPS data stored for debugging: {gps_ifd}")
                    
     
     
                    for tag, value in gps_ifd.items():
     
                        if tag in [1, 2, 3, 4, 'GPSLatitude', 'GPSLatitudeRef', 'GPSLongitude', 'GPSLongitudeRef']:
                            continue
                        
                        try:
                            if tag == 'GPSAltitude' and hasattr(value, 'numerator'):
                                exif_data['gps']['Altitude'] = f"{value.numerator/value.denominator:.1f}m"
                            elif tag == 'GPSSpeed' and hasattr(value, 'numerator'):
                                exif_data['gps']['Speed'] = f"{value.numerator/value.denominator:.1f}"
                            elif isinstance(value, bytes):
                                try:
                                    exif_data['gps'][str(tag)] = value.decode('utf-8', errors='ignore')
                                except:
                                    exif_data['gps'][str(tag)] = str(value)
                            else:
                                exif_data['gps'][str(tag)] = str(value)
                        except Exception as e:
                            logger.debug(f"Error processing GPS tag {tag}: {e}")
                            exif_data['gps'][str(tag)] = str(value)
                
                return exif_data
                
        except Exception as e:
            logger.error(f"EXIF extraction failed: {e}")
            return exif_data
    
    @staticmethod
    def update_gps_coordinates(image_path, latitude, longitude):
        """Update or add GPS coordinates to an image."""
        try:
            # Open original image
            img = Image.open(image_path)
            temp_jpeg_path = None

            # If not JPEG, convert to JPEG for EXIF support
            if img.format != 'JPEG':
                rgb = img.convert('RGB')
                temp_jpeg_path = image_path + "_converted.jpg"
                rgb.save(temp_jpeg_path, format='JPEG')
                # Use the converted file for piexif/load and for final save
                image_for_piexif = temp_jpeg_path
                img = Image.open(temp_jpeg_path)
            else:
                image_for_piexif = image_path

            # Load (possibly empty) EXIF dict and prepare GPS IFD
            exif_dict = piexif.load(image_for_piexif)

            lat_dms, lat_ref = EnhancedExifExtractor.decimal_to_dms(latitude, True)
            lon_dms, lon_ref = EnhancedExifExtractor.decimal_to_dms(longitude, False)

            gps_ifd = {
                piexif.GPSIFD.GPSVersionID: (2, 3, 0, 0),
                piexif.GPSIFD.GPSLatitudeRef: lat_ref.encode() if isinstance(lat_ref, str) else lat_ref,
                piexif.GPSIFD.GPSLatitude: lat_dms,
                piexif.GPSIFD.GPSLongitudeRef: lon_ref.encode() if isinstance(lon_ref, str) else lon_ref,
                piexif.GPSIFD.GPSLongitude: lon_dms,
            }

            exif_dict["GPS"] = gps_ifd
            exif_bytes = piexif.dump(exif_dict)

            # Save to BytesIO and return
            output = BytesIO()
            img.save(output, format='JPEG', exif=exif_bytes)
            output.seek(0)

            # Cleanup temp file if created
            if temp_jpeg_path and os.path.exists(temp_jpeg_path):
                try:
                    os.remove(temp_jpeg_path)
                except Exception:
                    pass

            return output

        except Exception as e:
            logger.error(f"Failed to update GPS coordinates: {e}")
            logger.debug(traceback.format_exc())
            return None


app = Flask(__name__)
ApplicationConfig.init_app(app)


@app.errorhandler(404)
def not_found_error(error):
    return render_template('index.html', error='Page not found'), 404

@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template('index.html', error='File too large. Maximum size is 16MB.'), 413

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return render_template('index.html', error='Internal server error occurred'), 500


@app.route('/', methods=['GET', 'POST'])
def index():
    """Main route - handles file upload and EXIF extraction."""
    if request.method == 'POST':
        filepath = None
        
        try:
            if 'photo' not in request.files:
                return render_template('index.html', error='No file uploaded. Please select a photo.')
            
            file = request.files['photo']
            
            if file.filename == '':
                return render_template('index.html', error='No file selected. Please choose a photo.')
            
            if not EnhancedExifExtractor.validate_file(file.filename):
                return render_template('index.html', error='Invalid file type. Please upload an image.')
            
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            file.save(filepath)
            logger.info(f"File saved: {filepath}")
            
            # Extract all EXIF data
            exif_data = EnhancedExifExtractor.extract_all_exif(filepath)
            
            # Prepare response data
            response_data = {
                'filename': filename,
                'exif_data': exif_data,
                'has_gps': bool(exif_data['gps'].get('latitude') and exif_data['gps'].get('longitude'))
            }
            
            if response_data['has_gps']:
                response_data['map_link'] = f"https://www.google.com/maps?q={exif_data['gps']['latitude']},{exif_data['gps']['longitude']}"
                response_data['latitude'] = round(exif_data['gps']['latitude'], 6)
                response_data['longitude'] = round(exif_data['gps']['longitude'], 6)
          
            
            with open(filepath, 'rb') as f:
                img_data = base64.b64encode(f.read()).decode()
                response_data['temp_image'] = img_data
            
            return render_template('index.html', **response_data, success=True)
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.error(traceback.format_exc())
            return render_template('index.html', error='An unexpected error occurred. Please try again.')
        
        finally:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.debug(f"Cleaned up: {filepath}")
                except Exception as e:
                    logger.error(f"Cleanup failed: {e}")
    
    return render_template('index.html')

@app.route('/update-gps', methods=['POST'])
def update_gps():
    """Update GPS coordinates in an image."""
    try:
        data = request.json
        image_data = base64.b64decode(data['image'])
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
        filename = data.get('filename', 'image.jpg')
        
        
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return jsonify({'error': 'Invalid coordinates'}), 400
        
        
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{filename}")
        with open(temp_path, 'wb') as f:
            f.write(image_data)
        
        
        output = EnhancedExifExtractor.update_gps_coordinates(temp_path, latitude, longitude)
        
        
        os.remove(temp_path)
        
        if output:
            return send_file(
                output,
                mimetype='image/jpeg',
                as_attachment=True,
                download_name=f"gps_updated_{filename}"
            )
        else:
            return jsonify({'error': 'Failed to update GPS coordinates'}), 500
            
    except Exception as e:
        logger.error(f"GPS update error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'environment': app.config['FLASK_ENV'],
        'timestamp': datetime.now().isoformat()
    }), 200


if __name__ == '__main__':
    logger.info("="*60)
    logger.info("GeoPhoto Enhanced Application Starting")
    logger.info(f"Environment: {app.config['FLASK_ENV']}")
    logger.info("="*60)
    
    if app.config['FLASK_ENV'] == 'development':
        app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=True)
    else:
        app.run(host='0.0.0.0', port=5000, debug=False)
