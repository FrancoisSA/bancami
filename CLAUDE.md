
Ce projet tourne sur la cible FSA-PI5


Github
https://github.com/FrancoisSA/bancami

Credentials                                                                                                                                                                         
  - Host : FSA-PI5.local, user : fsalazar, clé : ~/.ssh/id_ed25519   

Après une modification, déploie automatiquement et relance le serveur

  Pattern SSH one-liner                                                                                                                                                               
  ssh fsalazar@FSA-PI5.local "commande ici"                 

  Workflow de déploiement en 4 étapes : rclone copy → systemctl restart → status → journalctl.     
  Informe moi quand tu as relancé
  
  RELEASE
Lorsque je te demande de faire une release :
 - Relis le code pour trouver des problèmes de performance ou de sécurité et demande avant de modifier
 - Ajoute des commentaires pour qu'un humain puisse bien comprendre
 - Met à jour le manuel utilisateur qui porte le nom de l'appli et le numéro de version. Le format et en .MD il inclus la date et le numéro de version
 - Pousse une versio dans git. Si il n'y a pas de repository, demande si je veux le créer