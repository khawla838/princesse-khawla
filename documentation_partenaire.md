# Documentation Technique - Espace Partenaire

Ce document décrit de manière détaillée les tâches accomplies et les modifications apportées au code pour le module "Partenaire". Son but est de fournir à votre encadrant une vision claire sur ce qui a été ajouté, où se situent les changements et pourquoi.

---

## 1. Création du Modèle Partner et Gestion des Contrats

**Où chercher :** `partners/models.py`

**Ce qui a été ajouté :**
*   **Le modèle `Partner` :**
    *   Il est lié au `User` de base de Django via un `OneToOneField`. Cela permet de garder un système d'authentification standardisé.
    *   Gestion complète de la période d'essai de 6 mois grâce aux champs `is_trial`, `trial_start`, et `trial_end`.
    *   Logique de validation : le compte peut être certifié (`is_verified`), suspendu temporairement (`is_temporarily_disabled`) ou gelé (`account_frozen`) en cas de non-paiement.
*   **Le modèle `PartnerContract` :**
    *   Afin de conserver une traçabilité de la facturation, chaque période fait l'objet d'un contrat enregistré avec sa date de début, sa date de fin et le choix du paiement (`monthly` ou `total`).
    *   La validation du paiement d'un contrat via la fonction `mark_as_paid()` récupère automatiquement le paiement depuis Konnect (`konnect_payment_ref`) et réactive l'accès global du partenaire.

---

## 2. Ajout du Paiement Automatisé via Konnect

**Où chercher :** `partners/konnect.py`, `partners/views.py` et `partners/models.py`

**Ce qui a été ajouté :**
*   **Module API Konnect (`konnect.py`) :**
    *   `init_payment()` : Calcule le montant total en millimes et initie un lien de paiement avec Konnect, supportant différents types de paiement (Wallet, E-Dinar, Carte Bancaire).
    *   `verify_payment()` : Interroge le serveur de Konnect de manière sécurisée pour valider le statut `completed` de la transaction, évitant ainsi toute manipulation côté navigateur.
*   **Intégration aux Actions Clés :** 
    *   Ce processus de paiement protège désormais l'abonnement du partenaire (`PartnerContract`), mais aussi le système de Boost d'événements futures (`PartnerEvent.boost_price`) et l'achat de publicités payées.

---

## 3. Création du Dashboard Partenaire

Le Dashboard a été créé pour donner aux partenaires une interface d'autogestion qui vit indépendamment du panel d'administration classique. Les modèles, formulaires (dans `partners/forms.py`) et vues (dans `partners/views.py`) travaillent de concert.

### 3.1. Gestion des Événements (`PartnerEvent` et `PartnerEventMedia`)
*   **Informations de base :** Titre, description, dates, heures, lieu, et lien d'inscription gérés dans `PartnerEvent`.
*   **Upload de Médias :** Un modèle spécifique `PartnerEventMedia` a été créé pour permettre à un seul événement de posséder un nombre illimité d'images et de vidéos. Une validation stricte (`validate_image_or_video`) gère l'acceptation et catégorise dynamiquement l'attribut `media_type` côté modèle.
*   **Processus de Validation :** Chaque événement passe par une étape d'approbation (un statut : `pending`, `approved`, `rejected`), et peut être boosté si la date est >= 14 jours via le système de paiement.

### 3.2. Gestion des Publicités (`PartnerAd`)
*   **Adaptation au Format :** Le modèle `PartnerAd` exige spécifiquement un format mobile et un format tablette. Des validateurs côté Back-End ont été mis au point (`validate_mobile_image` et `validate_tablet_image`) pour imposer la limite de poids (5MB) et filtrer les extensions (GIF, JPG, etc.).
*   **Calcul des Tarifs :** Le prix est calculé dynamiquement grâce à la propriété `@property ad_price` qui croise le nombre de jours entre la date de début de campagne et sa fin, avec les tarifs du `PricingSettings`.

### 3.3. Gestion des Abonnements
*   Le script déclenche des alertes mensuelles (notifications de validation) pour tout ce qui concerne le renouvellement d'abonnement. 
*   Le partenaire a l'autonomie sur l'interface pour switcher entre l'option d'un paiement en ligne immédiat de la totalité et un système de prélèvements ou facturation mensuelle.

### 3.4. Gestion du Compte (Sécurité)
*   **Reset de mot de passe :** Intégré directement via un système de Token cryptographique (fonctions `generate_reset_token()` et `is_reset_token_valid()` du modèle Partner) expirant après 1 Heure.
*   **Changement d'email sécurisé :** Par mesure de précaution, la mise à jour d'un email enregistre la volonté via `pending_email` au lieu de l'appliquer immédiatement et lève une notification d'administration (`AdminNotification`).

---

## 4. API GraphQL pour Exposition vers le Frontend

**Où chercher :** `api/schema.py`

**Ce qui a été ajouté :**
Afin de ne rendre disponibles au Frontend que les données voulues et de garder une abstraction sécurisée de la base de données :
*   **Création des Types GraphQL Dédiés :** Nous avons complété l'architecture de données avec `PartnerEventAccountType`, `PartnerEventMediaType`, et `PartnerAdAccountType`.
*   **Assainissement des Données (Sérialiseurs) :** La logique est filtrée par les propriétés côté back (ex: `days_until_start`) et convertie via des helpers comme `_serialize_partner_event()`. De ce fait, seules les publicités actives et validées transitent sur le réseau. Un type `PartnerAccountPublicType` protège également les autres informations sensibles du profil.

---

## 5. Génération de Reçus de Paiement et Notifications par E-mail

Le système a été enrichi par de la communication directe avec les partenaires, matérialisée par l'envoi systématique d'emails et la création de reçus.

### 5.1. Création et Envoi des Reçus de Paiement (PDF)
**Où chercher :** `partners/receipt.py` et les modèles `Receipt`, `ReceiptHistory` (dans `models.py`)

*   **Calculs financiers automatiques :** Lors de chaque transaction réussie (Abonnement, Publicité, ou Boost d'événement), le module calcule automatiquement le montant Hors Taxe (HT), la TVA (19%), et le Timbre Fiscal (1.000 TND) avec précision monétaire.
*   **Génération dynamique de PDF :** Un document de reçu formaté au nom de l'entreprise ("Dacnis") est généré à la volée sous format PDF via la librairie `xhtml2pdf`. Il inclut un code client unique (`CL-XXXXXXXX`) et toutes les informations de transaction.
*   **Archivage et Envoi :** Le modèle `ReceiptHistory` garde une trace infalsifiable de toutes les factures. Simultanément, la fonction `send_receipt()` utilise `EmailMessage` pour envoyer automatiquement le fichier PDF en pièce jointe sur la boîte mail du partenaire.

### 5.2. Cycle de Notifications E-mail Automatiques
**Où chercher :** `partners/management/commands/check_expired_trials.py` et `partners/views.py`

Plusieurs déclencheurs garantissent que le partenaire soit prévenu aux moments importants :
*   **Alertes d'Expiration (Période d'Essai) :**
    *   **Email à J-30 :** Un rappel amical notifiant que la période d'essai de 6 mois expire dans 30 jours, incitant à s'abonner avec un lien direct vers le paiement.
    *   **Email à J-7 (Dernière relance) :** Un rappel urgent signalant que la suspension est imminente.
    *   **Email de Suspension :** Si aucun paiement n'est fait le jour J, le système envoie l'alerte confirmant la suspension ("Votre période d'essai a expiré, et le compte est actuellement désactivé") tout en bloquant l'accès système (`account_frozen = True`).
*   **E-mails de Sécurité :** À chaque demande de mot de passe oublié sur le Dashboard, un email incluant le lien unique généré par `generate_reset_token()` est adressé instantanément pour la réinitialisation de l'accès client.
