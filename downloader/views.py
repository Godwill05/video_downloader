from django.shortcuts import render
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .forms import VideoForm
import yt_dlp
import tempfile
import os
import json
import threading
import time
from urllib.parse import urlparse
import logging

# Configuration du logging
logger = logging.getLogger(__name__)

def index(request):
    form = VideoForm()
    return render(request, 'downloader/index.html', {'form': form})

@csrf_exempt
@require_http_methods(["POST"])
def get_video_info(request):
    """Récupère les informations de la vidéo sans la télécharger"""
    try:
        data = json.loads(request.body)
        url = data.get('url')
        
        if not url:
            return JsonResponse({'error': 'URL requise'}, status=400)
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return JsonResponse({'error': 'Impossible d\'extraire les informations de cette vidéo'}, status=400)
                
                # Extraire les formats disponibles
                formats = []
                audio_formats = []
                
                if 'formats' in info and info['formats']:
                    for fmt in info['formats']:
                        try:
                            # Format vidéo - vérifier que height existe et n'est pas None
                            if (fmt.get('vcodec') != 'none' and 
                                fmt.get('height') is not None and 
                                isinstance(fmt.get('height'), (int, float)) and
                                fmt.get('height') > 0):
                                formats.append({
                                    'format_id': fmt['format_id'],
                                    'ext': fmt.get('ext', 'mp4'),
                                    'height': int(fmt.get('height')),
                                    'fps': fmt.get('fps'),
                                    'filesize': fmt.get('filesize'),
                                    'quality': f"{int(fmt.get('height'))}p"
                                })
                            # Format audio - vérifier que c'est bien de l'audio pur
                            elif (fmt.get('acodec') != 'none' and 
                                  fmt.get('vcodec') == 'none' and
                                  fmt.get('abr') is not None and
                                  isinstance(fmt.get('abr'), (int, float)) and
                                  fmt.get('abr') > 0):
                                audio_formats.append({
                                    'format_id': fmt['format_id'],
                                    'ext': fmt.get('ext', 'mp3'),
                                    'abr': int(fmt.get('abr')),
                                    'filesize': fmt.get('filesize'),
                                })
                        except (TypeError, ValueError, KeyError):
                            # Ignorer les formats problématiques
                            continue
                
                # Trier par qualité - avec gestion sécurisée des None
                formats.sort(key=lambda x: x.get('height', 0), reverse=True)
                audio_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
                
                # Nettoyer et formater les données
                video_info = {
                    'title': str(info.get('title', 'Titre non disponible'))[:200],
                    'thumbnail': info.get('thumbnail') or '',
                    'duration': info.get('duration'),
                    'uploader': str(info.get('uploader', 'Inconnu'))[:100],
                    'view_count': info.get('view_count'),
                    'upload_date': info.get('upload_date') or '',
                    'description': str(info.get('description', ''))[:300] + ('...' if len(str(info.get('description', ''))) > 300 else ''),
                    'formats': formats[:10],
                    'audio_formats': audio_formats[:5],
                }
                
                return JsonResponse({'success': True, 'info': video_info})
                
            except yt_dlp.DownloadError as e:
                logger.error(f'Erreur yt-dlp dans get_video_info: {e}')
                return JsonResponse({'error': f'Erreur yt-dlp: {str(e)}'}, status=400)
            except Exception as e:
                logger.error(f'Erreur dans get_video_info: {e}')
                return JsonResponse({'error': f'Erreur d\'extraction: {str(e)}'}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Format JSON invalide'}, status=400)
    except Exception as e:
        logger.error(f'Erreur générale dans get_video_info: {e}')
        return JsonResponse({'error': f'Erreur serveur: {str(e)}'}, status=500)

@csrf_exempt 
@require_http_methods(["POST"])
def download_video(request):
    """Télécharge la vidéo avec les paramètres spécifiés"""
    try:
        # Log des données reçues pour debug
        logger.info(f"POST data: {request.POST}")
        
        # Validation manuelle des données si le form échoue
        url = request.POST.get('url', '').strip()
        format_type = request.POST.get('format_type', 'video')
        quality = request.POST.get('quality', 'best')
        audio_quality = request.POST.get('audio_quality', 'best')
        
        # Validation basique
        if not url:
            return JsonResponse({'error': 'URL requise'}, status=400)
        
        if format_type not in ['video', 'audio']:
            return JsonResponse({'error': 'Type de format invalide'}, status=400)
        
        logger.info(f"Processing download: URL={url}, format_type={format_type}, quality={quality}, audio_quality={audio_quality}")
        
        # Créer un répertoire temporaire
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Temporary directory created: {temp_dir}")
        
        try:
            # Configuration yt-dlp selon le type de fichier
            if format_type == 'audio':
                # Utiliser audio_quality pour l'audio
                audio_qual = audio_quality if audio_quality != 'best' else '320'
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': audio_qual,
                    }],
                    'quiet': False,  # Activer les logs pour debug
                    'no_warnings': False,
                    'ignoreerrors': False,
                }
                file_extension = 'mp3'
                logger.info(f"Audio download configured with quality: {audio_qual}")
            else:
                # Format vidéo - utiliser quality pour la vidéo
                if quality == 'best':
                    format_selector = 'best[ext=mp4]/best'
                else:
                    height = quality.replace('p', '')
                    format_selector = f'best[height<={height}][ext=mp4]/best[height<={height}]/best[ext=mp4]/best'
                
                ydl_opts = {
                    'format': format_selector,
                    'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                    'quiet': False,  # Activer les logs pour debug
                    'no_warnings': False,
                    'ignoreerrors': False,
                }
                file_extension = 'mp4'
                logger.info(f"Video download configured with format: {format_selector}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extraire les informations pour le nom du fichier
                try:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', 'video')
                    logger.info(f"Video title: {title}")
                except Exception as e:
                    logger.warning(f"Could not extract title: {e}")
                    title = 'video'
                
                # Nettoyer le titre pour le nom de fichier
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
                if not safe_title:
                    safe_title = 'video'
                filename = f"{safe_title[:50]}.{file_extension}"
                logger.info(f"Safe filename: {filename}")
                
                # Télécharger
                logger.info("Starting download...")
                ydl.download([url])
                logger.info("Download completed")
                
                # Trouver le fichier téléchargé
                downloaded_files = [f for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f))]
                logger.info(f"Downloaded files: {downloaded_files}")
                
                if not downloaded_files:
                    logger.error("No files downloaded")
                    return JsonResponse({'error': 'Aucun fichier téléchargé'}, status=500)
                
                # Prendre le premier fichier trouvé
                downloaded_file = os.path.join(temp_dir, downloaded_files[0])
                logger.info(f"Downloaded file path: {downloaded_file}")
                
                # Vérifier que le fichier existe et n'est pas vide
                if not os.path.exists(downloaded_file):
                    logger.error(f"File does not exist: {downloaded_file}")
                    return JsonResponse({'error': 'Le fichier téléchargé est inexistant'}, status=500)
                
                file_size = os.path.getsize(downloaded_file)
                logger.info(f"File size: {file_size} bytes")
                
                if file_size == 0:
                    logger.error("Downloaded file is empty")
                    return JsonResponse({'error': 'Le fichier téléchargé est vide'}, status=500)
                
                # Préparer la réponse de téléchargement
                response = FileResponse(
                    open(downloaded_file, 'rb'),
                    as_attachment=True,
                    filename=filename,
                    content_type='application/octet-stream'
                )
                
                logger.info(f"Sending file response: {filename}")
                
                # Nettoyer les fichiers temporaires après l'envoi
                def cleanup():
                    try:
                        time.sleep(10)  # Attendre que le téléchargement soit terminé
                        for file in os.listdir(temp_dir):
                            file_path = os.path.join(temp_dir, file)
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                        os.rmdir(temp_dir)
                        logger.info(f"Cleaned up temporary directory: {temp_dir}")
                    except Exception as cleanup_error:
                        logger.error(f"Erreur lors du nettoyage: {cleanup_error}")
                
                threading.Thread(target=cleanup, daemon=True).start()
                
                return response
                
        except yt_dlp.DownloadError as e:
            logger.error(f"yt-dlp download error: {e}")
            # Nettoyer en cas d'erreur
            try:
                for file in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, file))
                os.rmdir(temp_dir)
            except:
                pass
            return JsonResponse({'error': f'Erreur de téléchargement yt-dlp: {str(e)}'}, status=500)
        
        except Exception as e:
            logger.error(f"General error in download process: {e}")
            # Nettoyer en cas d'erreur
            try:
                for file in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, file))
                os.rmdir(temp_dir)
            except:
                pass
            return JsonResponse({'error': f'Erreur lors du téléchargement: {str(e)}'}, status=500)
            
    except Exception as e:
        logger.error(f"Erreur serveur générale: {e}")
        return JsonResponse({'error': f'Erreur serveur lors du téléchargement: {str(e)}'}, status=500)