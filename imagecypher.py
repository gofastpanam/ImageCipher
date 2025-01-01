#!/usr/bin/env python3
"""
ImageCypher - Application de stéganographie sécurisée pour cacher des messages dans des images.

Ce module fournit des fonctions pour encoder et décoder des messages secrets dans des
images en utilisant la technique LSB (Least Significant Bit) avec chiffrement AES.
"""

import os
import sys
from pathlib import Path
from typing import Union, Tuple
from PIL import Image
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

# Constantes de sécurité
MAX_MESSAGE_LENGTH = 1024 * 1024  # 1 MB
ALLOWED_IMAGE_FORMATS = {'.png', '.jpg', '.jpeg', '.bmp'}
SALT = b'ImageCypherSalt'  # Dans une vraie application, ce devrait être unique par utilisateur

def generate_key(password: str) -> bytes:
    """
    Génère une clé de chiffrement à partir d'un mot de passe.
    
    Args:
        password (str): Mot de passe pour générer la clé
        
    Returns:
        bytes: Clé de chiffrement
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def validate_file_path(file_path: Union[str, Path], must_exist: bool = True) -> Path:
    """
    Valide et normalise un chemin de fichier.
    
    Args:
        file_path: Chemin du fichier à valider
        must_exist: Si True, vérifie que le fichier existe
        
    Returns:
        Path: Chemin normalisé
        
    Raises:
        ValueError: Si le chemin est invalide ou le fichier n'existe pas
    """
    try:
        path = Path(file_path).resolve()
        if must_exist and not path.is_file():
            raise ValueError(f"Le fichier {file_path} n'existe pas")
        if path.suffix.lower() not in ALLOWED_IMAGE_FORMATS:
            raise ValueError(f"Format de fichier non supporté. Formats acceptés : {', '.join(ALLOWED_IMAGE_FORMATS)}")
        return path
    except Exception as e:
        raise ValueError(f"Chemin de fichier invalide : {str(e)}")

def secure_encode_image(image_path: Union[str, Path], message: str, output_path: Union[str, Path], password: str) -> None:
    """
    Encode et chiffre un message secret dans une image.

    Args:
        image_path: Chemin vers l'image source
        message: Message secret à cacher
        output_path: Chemin où sauvegarder l'image
        password: Mot de passe pour le chiffrement
        
    Raises:
        ValueError: Si les paramètres sont invalides
        IOError: Si une erreur survient lors de la manipulation des fichiers
    """
    try:
        # Validation des entrées
        if not message or len(message.encode()) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Le message doit faire moins de {MAX_MESSAGE_LENGTH // 1024} KB")
        
        input_path = validate_file_path(image_path)
        output_path = validate_file_path(output_path, must_exist=False)
        
        # Chiffrement du message
        f = Fernet(generate_key(password))
        encrypted_message = f.encrypt(message.encode())
        binary_message = ''.join(format(b, '08b') for b in encrypted_message) + '1' * 8  # Marqueur de fin
        
        with Image.open(input_path) as img:
            # Vérification de la capacité
            width, height = img.size
            if len(binary_message) > width * height * 3:
                raise ValueError("Message trop long pour cette image")
            
            # Création d'une copie pour l'encodage
            encoded = img.copy()
            data_index = 0
            
            # Encodage du message chiffré
            for y in range(height):
                for x in range(width):
                    pixel = list(img.getpixel((x, y)))
                    for i in range(3):
                        if data_index < len(binary_message):
                            pixel[i] = (pixel[i] & ~1) | int(binary_message[data_index])
                            data_index += 1
                    encoded.putpixel((x, y), tuple(pixel))
                    if data_index >= len(binary_message):
                        break
                if data_index >= len(binary_message):
                    break
            
            # Sauvegarde sécurisée
            encoded.save(output_path)
            
        print("Message caché dans l'image avec succès.")
        
    except Exception as e:
        print(f"Erreur lors de l'encodage : {str(e)}")
        # Nettoyage en cas d'erreur
        if 'encoded' in locals():
            del encoded
        if 'output_path' in locals() and Path(output_path).exists():
            os.remove(output_path)
        raise

def secure_decode_image(image_path: Union[str, Path], password: str) -> str:
    """
    Décode et déchiffre un message caché dans une image.

    Args:
        image_path: Chemin vers l'image contenant le message
        password: Mot de passe pour le déchiffrement
        
    Returns:
        str: Message secret décodé
        
    Raises:
        ValueError: Si les paramètres sont invalides
        IOError: Si une erreur survient lors de la lecture du fichier
    """
    try:
        input_path = validate_file_path(image_path)
        f = Fernet(generate_key(password))
        
        binary_message = ''
        encrypted_bytes = bytearray()
        
        with Image.open(input_path) as img:
            # Extraction des bits
            for y in range(img.height):
                for x in range(img.width):
                    pixel = img.getpixel((x, y))
                    for i in range(3):
                        binary_message += str(pixel[i] & 1)
                        
                        # Conversion en bytes tous les 8 bits
                        if len(binary_message) >= 8:
                            byte_val = int(binary_message[:8], 2)
                            binary_message = binary_message[8:]
                            
                            # Vérification du marqueur de fin
                            if byte_val == 255:  # Tous les bits à 1
                                return f.decrypt(bytes(encrypted_bytes)).decode()
                            
                            encrypted_bytes.append(byte_val)
                            
        raise ValueError("Aucun message trouvé dans l'image")
        
    except Exception as e:
        print(f"Erreur lors du décodage : {str(e)}")
        raise

def main():
    """Point d'entrée principal du programme avec interface sécurisée."""
    try:
        print("=== ImageCypher - Stéganographie Sécurisée ===")
        print("1. Encoder un message")
        print("2. Décoder un message")
        
        choix = input("\nChoisissez une option (1/2) : ").strip()
        
        if choix == '1':
            image_path = input("Chemin de l'image source : ").strip()
            message = input("Message secret : ").strip()
            output_path = input("Chemin pour sauvegarder l'image encodée : ").strip()
            password = input("Mot de passe de chiffrement : ").strip()
            
            if not all([image_path, message, output_path, password]):
                raise ValueError("Tous les champs sont obligatoires")
                
            secure_encode_image(image_path, message, output_path, password)
            
        elif choix == '2':
            image_path = input("Chemin de l'image encodée : ").strip()
            password = input("Mot de passe de déchiffrement : ").strip()
            
            if not all([image_path, password]):
                raise ValueError("Tous les champs sont obligatoires")
                
            secret_message = secure_decode_image(image_path, password)
            print("\nMessage secret décodé :", secret_message)
            
        else:
            print("Option invalide. Veuillez choisir 1 ou 2.")
            
    except Exception as e:
        print(f"\nErreur : {str(e)}")
        print("Le programme s'est terminé avec une erreur.")
        sys.exit(1)

if __name__ == "__main__":
    main()
