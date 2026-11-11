# Lecteur Dolby Digital (AC-3) — décodeur écrit à la main
Décodeur AC-3 en Python/NumPy d'après ATSC A/52:2018 (`ac3/decoder.py`), tables extraites de la norme par `tools_gen_tables.py`.
Effets : dialnorm, compression dynamique (dynrng/compr), mixage LoRo / LtRt (Dolby Surround) / mono / 5.1.
Sources prises en charge : .ac3, MP4/MOV, MKV/WebM (pistes AC-3). Non pris en charge : E-AC-3, TrueHD, Atmos, MPEG-PS/TS.
La vidéo est lue par libmpv (qui contient ses propres bibliothèques vidéo) ; l'audio AC-3 n'utilise aucun code FFmpeg.
Build : onglet Actions > "Build Windows" > Run workflow. Local : `pip install -r requirements.txt`, `libmpv-2.dll` à côté de main.py, `python main.py`.
Tests (FFmpeg requis, test uniquement) : `python tools_test.py` et `python tools_test2.py`.
