import base64
import re
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import pwinput

salt = b"parlaConIO"
def kdf():
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
        )

def ottieni_chiave(stringa):
    '''Ottiene la chiave crittografica a partire da una stringa'''
    x = base64.urlsafe_b64encode(kdf().derive(stringa))
    return x

def imposta_password():
    '''Chiede all'utente di impostare una password sicura
    e restituisce la chiave crittografica derivata'''
    RE_PASSWORD = "^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[!#$%&@.,\[\]-_?].*)(?=.*[\W]).{8,20}$"
    password_1 = ""
    while bool(re.match(RE_PASSWORD, password_1)) is False:
        print("Scegli una password. Fra 8 e 20 caratteri con una maiuscola, "\
              "una minuscola, un numero e un carattere speciale.")
        password_1 = pwinput.pwinput(prompt = "Scegli una password: ")
        password_2 = pwinput.pwinput(prompt= "Ripeti la password: ")
        while password_1 != password_2:
            print("Le password non coincidono. Ripeti.")
            password_1 = pwinput.pwinput(prompt = "Scegli una password: ")
            password_2 = pwinput.pwinput(prompt= "Ripeti la password: ")
        if bool(re.match(RE_PASSWORD, password_1)) is False:
            print("Password debole. Ripeti.")
    parola = password_1.encode()
    x = base64.urlsafe_b64encode(kdf().derive(parola))
    password_1 = ""
    password_2 = ""
    parola = b""
    return x

def cifra_file(file_da_cifrare, chiave, output_file = ""):
    '''Cifra un file in un altro file'''
    if output_file == "":
        output_file = file_da_cifrare
    with open(file_da_cifrare, "rb") as f:
        originale = f.read()
    fernet = Fernet(chiave)
    cifrato = fernet.encrypt(originale)
    with open(output_file, "wb") as f:
        f.write(cifrato)

def decifra_dizionario(input_file, chiave):
    '''Decifra un dizionario memorizzato in un file JSON'''
    fernet = Fernet(chiave)
    with open(input_file, "rb") as f:
        a = f.read()
        b = fernet.decrypt(a)
        c = b.decode()
        d = json.loads(c)
    return d

chiave = imposta_password()
cifra_file("IO.chiaro.cfg", chiave, "IO.master.cfg")
cifra_file("pagoPA.chiaro.cfg", chiave, "pagoPA.master.cfg")
cifra_file("permessi.chiaro.cfg", chiave, "permessi.master.cfg")

decifra_dizionario("IO.master.cfg", chiave)
decifra_dizionario("pagoPA.master.cfg", chiave)
decifra_dizionario("permessi.master.cfg", chiave)

print("Fatto!")
input ("Premi INVIO/ENTER per terminare.")

