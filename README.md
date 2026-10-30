# DualSubs pour Kodi

DualSubs est une extension expérimentale pour Kodi qui permet d’afficher deux pistes de sous-titres textuels pendant la lecture d’une vidéo : la piste principale est affichée par Kodi et la seconde est affichée en surimpression par DualSubs.

Le projet a été développé et essayé sur **Raspberry Pi 5**, avec **LibreELEC 12.0.2** et **Kodi 21.2**. Il s’agit d’un prototype : son fonctionnement peut varier selon le fichier vidéo, ses pistes et la façon dont Kodi y accède.

## Avant de commencer

- Un appareil sous LibreELEC avec Kodi 21 ou une version compatible. La configuration de référence est un Raspberry Pi 5 sous LibreELEC 12.0.2 / Kodi 21.2.
- Une vidéo contenant au moins deux pistes de sous-titres **textuels** intégrées.
- L’extension de programme **FFmpeg Tools** installée depuis le dépôt officiel LibreELEC. DualSubs s’en sert pour extraire la seconde piste.

Les sous-titres graphiques (par exemple PGS ou VobSub) ne sont pas pris en charge. DualSubs ne télécharge aucune vidéo ni aucun sous-titre depuis Internet : il traite les pistes du fichier que Kodi est en train de lire.

## Installation depuis un fichier ZIP

1. Télécharge le fichier ZIP de DualSubs depuis la rubrique [Releases](https://github.com/RomainDemeusoit/dualsubs-kodi/releases) du dépôt.
2. Dans Kodi, ouvre **Paramètres → Système → Extensions** et active **Sources inconnues** si Kodi le demande.
3. Ouvre **Extensions → Installer depuis un fichier ZIP**.
4. Sélectionne le fichier ZIP téléchargé.
5. Dans **Extensions → Installer depuis un dépôt → Dépôt LibreELEC → Extensions de programmes**, installe **FFmpeg Tools** si ce n’est pas déjà fait.

Les intitulés peuvent légèrement varier selon la langue et l’apparence de Kodi. L’installation manuelle d’un ZIP ne met pas automatiquement l’extension à jour : il faut installer le ZIP d’une nouvelle version lorsqu’elle est publiée.

## Utilisation

1. Lance une vidéo contenant au moins deux pistes de sous-titres textuels.
2. Ouvre **Extensions → Extensions de programmes → DualSubs** pendant que la vidéo est en cours.
3. Choisis la piste principale, affichée en bas par Kodi.
4. Choisis la piste secondaire, affichée en haut par DualSubs.
5. Patiente pendant l’extraction. La durée dépend notamment de la taille du fichier et de son emplacement.

Pour arrêter l’affichage de la seconde piste, quitte la lecture de la vidéo ou relance DualSubs pour une autre vidéo.

## Ce que fait l’extension

Kodi affiche une piste de sous-titres intégrée à la vidéo. L’extension utilise FFmpeg Tools pour extraire l’autre piste textuelle dans un fichier temporaire, puis l’affiche comme texte synchronisé pendant la lecture. Le fichier vidéo original n’est pas modifié.

Le code source se trouve dans [`script.dualsubs/`](script.dualsubs/). Le point d’entrée est [`default.py`](script.dualsubs/default.py) et les informations de l’extension sont dans [`addon.xml`](script.dualsubs/addon.xml).

## Limites connues

- Le projet est un prototype et n’a été vérifié que dans un environnement limité. Les autres appareils, versions de Kodi, interfaces graphiques et méthodes de stockage doivent être testés séparément.
- La compatibilité dépend du conteneur vidéo, du codec des sous-titres, des métadonnées que Kodi expose et de la capacité de FFmpeg à lire le chemin du fichier.
- Seuls les sous-titres textuels convertibles par FFmpeg sont visés. Les pistes graphiques ne sont pas prises en charge ; les styles avancés de certains formats peuvent être simplifiés lors de la conversion en SRT.
- L’extraction peut prendre du temps, en particulier pour les gros fichiers ou les supports réseau. Elle est relancée lors d’une nouvelle utilisation et n’est pas mise en cache.
- L’extension doit être lancée manuellement pendant la lecture. L’affichage de la surimpression peut dépendre du rendu vidéo et de l’interface Kodi utilisée.
- L’extension ne garantit pas la prise en charge de tous les formats vidéo lisibles par Kodi.

## Signaler un problème

Avant de signaler un problème, indique si possible :

- la version de Kodi et de LibreELEC, ainsi que le modèle de l’appareil ;
- le conteneur du fichier (par exemple MKV ou MP4) et le type de sous-titres (textuels ou graphiques) ;
- l’étape où le problème apparaît et le texte exact du message d’erreur.

Ne joins pas de film, de sous-titre protégé par le droit d’auteur, de mot de passe ni d’autre information privée. Tu peux ouvrir un ticket dans [Issues](https://github.com/RomainDemeusoit/dualsubs-kodi/issues).

## Licence

DualSubs est distribué sous licence MIT. Consulte le fichier [`LICENSE`](LICENSE).
