from django import forms
import re

class VideoForm(forms.Form):
    url = forms.URLField(
        label='URL de la vidéo',
        widget=forms.URLInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all duration-200',
            'placeholder': 'Collez l\'URL YouTube, TikTok, Instagram...',
            'id': 'video-url'
        })
    )
    
    format_type = forms.ChoiceField(
        label='Type de fichier',
        choices=[
            ('video', 'Vidéo (MP4)'),
            ('audio', 'Audio (MP3)'),
        ],
        initial='video',
        widget=forms.RadioSelect(attrs={
            'class': 'format-radio'
        })
    )
    
    quality = forms.ChoiceField(
        label='Qualité',
        choices=[
            ('best', 'Meilleure qualité disponible'),
            ('1080p', '1080p (Full HD)'),
            ('720p', '720p (HD)'),
            ('480p', '480p (SD)'),
            ('360p', '360p (Mobile)'),
        ],
        initial='best',
        required=False,  # Ajouté pour éviter les erreurs
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all duration-200'
        })
    )
    
    audio_quality = forms.ChoiceField(
        label='Qualité audio',
        choices=[
            ('best', 'Meilleure qualité'),
            ('320', '320 kbps'),
            ('256', '256 kbps'),
            ('128', '128 kbps'),
            ('96', '96 kbps'),
        ],
        initial='best',
        required=False,  # Ajouté pour éviter les erreurs
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all duration-200'
        })
    )

    def clean_url(self):
        url = self.cleaned_data.get('url')
        if not url:
            raise forms.ValidationError("L'URL est requise.")
        
        # Validation basique des URLs supportées
        supported_patterns = [
            r'(youtube\.com|youtu\.be)',
            r'(tiktok\.com)',
            r'(instagram\.com)',
            r'(twitter\.com|x\.com)',
            r'(facebook\.com)',
            r'(vimeo\.com)',
            r'(fr.pornhub\.com)',
        ]
        
        if not any(re.search(pattern, url, re.IGNORECASE) for pattern in supported_patterns):
            raise forms.ValidationError("URL non supportée. Utilisez YouTube, TikTok, Instagram, Twitter, Facebook ou Vimeo.")
        
        return url

    def clean(self):
        cleaned_data = super().clean()
        format_type = cleaned_data.get('format_type')
        quality = cleaned_data.get('quality')
        audio_quality = cleaned_data.get('audio_quality')
        
        # Validation conditionnelle selon le type de format
        if format_type == 'video':
            if quality:
                valid_qualities = ['best', '1080p', '720p', '480p', '360p']
                if quality not in valid_qualities:
                    raise forms.ValidationError("Qualité vidéo invalide.")
        elif format_type == 'audio':
            if audio_quality:
                valid_qualities = ['best', '320', '256', '128', '96']
                if audio_quality not in valid_qualities:
                    raise forms.ValidationError("Qualité audio invalide.")
        
        return cleaned_data

    def clean_quality(self):
        quality = self.cleaned_data.get('quality')
        # Permettre une validation plus flexible
        if quality:
            valid_qualities = ['best', '1080p', '720p', '480p', '360p']
            if quality not in valid_qualities:
                raise forms.ValidationError("Qualité invalide.")
        return quality

    def clean_audio_quality(self):
        audio_quality = self.cleaned_data.get('audio_quality')
        # Permettre une validation plus flexible
        if audio_quality:
            valid_qualities = ['best', '320', '256', '128', '96']
            if audio_quality not in valid_qualities:
                raise forms.ValidationError("Qualité audio invalide.")
        return audio_quality