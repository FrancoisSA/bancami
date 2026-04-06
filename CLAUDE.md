
Ce projet tourne sur la cible FSA-PI5

Credentials                                                                                                                                                                         
  - Host : FSA-PI5.local, user : fsalazar, clé : ~/.ssh/id_ed25519   

Après une modification, déploie automatiquement et relance le serveur

  Pattern SSH one-liner                                                                                                                                                               
  ssh fsalazar@FSA-PI5.local "commande ici"                 

  Workflow de déploiement en 4 étapes : rclone copy → systemctl restart → status → journalctl.     
  Informe moi quand tu as relancé
  