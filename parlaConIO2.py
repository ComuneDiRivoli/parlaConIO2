## Autore: Francesco Del Castillo (2023)
import datetime
import time
import sys
import uuid
import os
import base64
import socket
import json
import csv
import re
import inspect
import logging  #per log di requests
from jose import jwt
from jose.constants import Algorithms
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import requests
import pwinput
import pyinputplus as pyip

BASE_URL_IO = "https://api.io.italia.it/api/v1" # url di base dei web service IO
logFileName="appIO.log"

################################
## COSTANTI LEGATE ALL'ENTE   ##
## --> compilarle e           ##
##         verificare i testi ##
################################

ENTE = "Comune di Rivoli"
L_ENTE = "il Comune di Rivoli"
LL_ENTE = "Il Comune di Rivoli"
DELL_ENTE = "del Comune di Rivoli"
ALL_ENTE = "al Comune di Rivoli"
DALL_ENTE = "dal Comune di Rivoli"

URL_PAGAMENTI = "https://portale.comune.rivoli.to.it"
URL_PRENOTAZIONE_CIE = "https://prenota.comune.rivoli.to.it/anagrafe-e-stato-civile/18/calendar"

ENTE_IO_CIE = "SCI" #Servizio IO per messaggi scadenza carta di identità
ENTE_IO_PEC = "COM" #Servizio IO per messaggi scadenza casella PEC

#Regole per il logging delle chiamate requests
#logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("urllib3")
log.setLevel(logging.DEBUG)

# FUNZIONI E VARIABILI GLOBALI PER INTERAZIONE CON L'UTENTE

def getIPAddress():
    return socket.gethostbyname(socket.gethostname())

CALLING_IP = getIPAddress()
CALLING_USER = os.getlogin()

def attendi():
    '''Richiede un'interazione dell'utente per proseguire'''
    input("Premi INVIO/ENTER per proseguire.")

def termina():
    '''Richiede un'interazione dell'utente per terminare il programma
    Utile anche a fine sCrIpt per evitare di perdere quanto scritto a video'''
    input("Premi INVIO/ENTER per terminare.")
    sys.exit()
    
def timestamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")

def timestamp_breve():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

LISTA_RISP = ["sì", "SI", "S", "s", "Sì", "OK", "si", "NO", "no", "n", "N"]
LISTA_OK = ["sì", "SI", "S", "s", "Sì", "OK", "si"] # elenco di parola da interpretare come risposta affermativa in caso di domanda posta dal programma


RE_CF = "^([0-9]{11})|([A-Za-z]{6}[0-9]{2}[A-Za-z]{1}[0-9]{2}[A-Za-z]{1}[0-9]{3}[A-Za-z]{1})$"
RE_MAIL = "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

def chiedi_cf():
    '''Chiede di inserire un codice fiscale / partita IVA e valida il formato.'''
    ottieni_cf = False
    while ottieni_cf is False:
        x = input("Inserisci il codice fiscale per cui verificare il domicilio digitale: ")
        if re.match(RE_CF, x):
            ottieni_cf = True
        else:
            print("Codice fiscale non valido.")
    return x

def chiedi_mail():
    '''Chiede di inserire un indirizzo e-mail e valida il formato.'''
    ottieni_mail = False
    while ottieni_mail is False:
        x = input("Inserisci l\'indirizzo PEC da verificare: ")
        if re.match(RE_MAIL, x):
            ottieni_mail = True
        else:
            print("Formato indirizzo PEC non valido.")
    return x

def chiedi_data():
    '''Chiede di inserire una data G/M/A o G-M-A
    e la restituisce AAAA-MM-GG'''
    x = pyip.inputDate(prompt = "Inserisci la data alla quale verificare: ",
        formats=["%d/%m/%y", "%d/%m/%Y", "%d-%m-%y", "%d-%m-%Y"])
    y = x.strftime("%Y-%m-%d")
    return y

def data(data): #converte uan stringa che indica una data nel forma gg/mm/aaaa nel formato ISO 8601 (richiesto dalle API IO) - ore 0:00 
    stringa = data
    date_object = datetime.datetime.strptime(stringa, "%d/%m/%Y")
    return date_object.strftime('%Y-%m-%dT%H:%M:%S.000Z')

def data2(data): #converte uan stringa che indica una data nel forma gg/mm/aaaa nel formato ISO 8601 (richiesto dalle API IO) - ore 18:00 
    stringa = data
    date_object = datetime.datetime.strptime(stringa, "%d/%m/%Y")
    return date_object.strftime('%Y-%m-%dT18:00:00.000Z')

def logRequest(logFile, requestTime, verbo, metodo, info):
    rigaDiLog=[requestTime, CALLING_IP, CALLING_USER, verbo, metodo, info]
    logFile.write(";".join(rigaDiLog))
    logFile.write("\n")
    logFile.flush()

def logResponse(logFile, responseTime, requestTime, status_code, info):
    rigaDiLog=[responseTime, CALLING_IP, requestTime, str(status_code), info]
    logFile.write(";".join(rigaDiLog))
    logFile.write("\n")
    logFile.flush()

def logga(stringa, file_di_log = None):
    '''Scrive una stringa nel log di lotto'''
    file_di_log = file_di_log or LOTTO_LOG
    with open(file_di_log, "a+") as file:
        riga_di_log=[timestamp(),stringa]
        file.write(";".join(riga_di_log))
        file.write("\n")
        file.flush()

def stampa(stringa, file_di_log = None):
    '''Scrive una stringa a schermo e nel log di lotto'''
    file_di_log = file_di_log or LOTTO_LOG
    print(stringa)
    with open(file_di_log, "a+") as file:
        riga_di_log=[timestamp(),stringa]
        file.write(";".join(riga_di_log))
        file.write("\n")
        file.flush()

## Funzioni crittografiche
def cifra_stringa(stringa, chiave):
    '''Cifra una stringa con la chiave indicata'''
    fernet = Fernet(chiave)
    fernet.encrypt(stringa.encode())

def decifra_stringa(stringa, chiave):
    '''Decifra una stringa cifrata tramite la chiave indicata'''
    fernet = Fernet(chiave)
    fernet.decrypt(stringa).decode()

def cifra_dizionario(diz, chiave, output_file):
    '''Salva un dizionario diz nel file output_file cifrato con la chiave "chiave" '''
    fernet = Fernet(chiave)
    a = json.dumps(diz, indent=4).encode()
    b =fernet.encrypt(a)
    with open(output_file, "wb") as f:
        f.write(b)

def decifra_dizionario(input_file, chiave):
    '''Decifra un dizionario memorizzato in un file JSON'''
    fernet = Fernet(chiave)
    with open(input_file, "rb") as f:
        a = f.read()
        b = fernet.decrypt(a)
        c = b.decode()
        d = json.loads(c)
    return d

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

def decifra_file(file_da_decifrare, chiave, output_file = ""):
    '''Decifra un file in un altro file'''
    if output_file == "":
        output_file = file_da_decifrare
    with open(file_da_decifrare, "rb") as f:
        cifrato = f.read()
    fernet = Fernet(chiave)
    originale = fernet.decrypt(cifrato)
    with open(output_file, "wb") as f:
        f.write(originale)

def ricifra_file(file_da_ricifrare, chiave1, chiave2, output_file):
    '''Decifra un file cifrato con chiave 1 o la cifra con chiave2'''
    with open(file_da_ricifrare, "rb") as f:
        cifrato = f.read()
        fernet = Fernet(chiave1)
        in_chiaro = fernet.decrypt(cifrato)
        fernet = Fernet(chiave2)
        ricifrato = fernet.encrypt(in_chiaro)
    with open(output_file, "wb") as f:
        f.write(ricifrato)

def ottieni_apikey(servizio_io, chiave=None):
    '''Da codice del servizio IO a APIKEY.
    Ottine la APIKEY del servizio_io dal file IO.cfg decifrato con chiave'''
    chiave = chiave or CHIAVE
    with open("IO.cfg", "rb") as file:
        apik = decifra_dizionario("IO.cfg", chiave)[servizio_io]["APIKEY"]
    return apik

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

## Funzioni che servono per la manipolazione di file di input e di output
def crea_cartella(descrizione, data_e_ora=timestamp_breve()):
    '''Crea una sottocartella nella cartella di esecuzione dello script
    Se l'argomento data_e_ora è nullo, usa un timestamp breve al suo posto.'''
    path="./lotti/" + data_e_ora + "-" + descrizione + "/"
    if not os.path.isdir(path):
        os.mkdir(path)
    return path

def salva_dizionario(dizionario, file_out):
    '''Salva un dizionario in un file JSON'''
    with open(file_out, "w+") as file:
        file.write(json.dumps(dizionario, sort_keys=False, indent=4))

def chiedi_nome_file_dati():
    '''Ottiene il nome del file CSV con i dati.'''
    nome_file = input("Indica il nome del file CSV: ")
    file_trovato = False
    while file_trovato is False:
        if os.path.exists(nome_file):
            file_trovato = True
            print("File trovato.")
        else:
            nome_file = input(
                "File "+ nome_file + " non trovato. "\
                "\nVerifica e inserisci di nuovo il nome del file CSV: "
                )
    print("File CSV trovato.\n")
    return nome_file
  
def importa_dati_csv(nome_file, nome_file_output):
    '''Importa un file csv e restituisce il dizionario corrispondente
    e la lista di etichette/colonne del CSV. Salva il dizionario in un file JSON.'''
    with open(nome_file, "r") as input_file:
        reader = csv.DictReader(input_file, delimiter=";")
        dizionario = []
        for i in reader:
            dizionario.append(i)
    salva_dizionario(dizionario, nome_file_output)
    if dizionario != []:
        etichette_csv = list(dizionario[0].keys())
    else:
        etichette_csv = []
    return dizionario, etichette_csv

## Funzioni per generare il corpo del messaggio
def recupera_argomenti(funzione):
    '''Recupera gli argomenti attesi da una funzione - per creare le corrispondenze'''
    argomenti = inspect.getfullargspec(funzione).args
    return argomenti

def mappa(argomenti, etichette):
    '''Guida l'utente nel 'mappare' gli argomenti richiesti da una funzione di composizione
    di un messaggio e le colonne del file CSV con i dati'''
    corrispondenze = {}
    for i in argomenti:
        corrispondenze[i] = ''
    for i in argomenti:
        if i in etichette:
            corrispondenze[i] = i
    print("-------- \nGli ARGOMENTI richiesti dalla funzione sono:")
    for i in argomenti:
        print(i)
    print("-------- \nLe ETICHETTE disponibili sono:")
    for i in etichette:
        print(i)
    print("-------- \nPer ogni argomento indica l'etichetta da utilizzare (INVIO per confermare la proposta)")
    for i in argomenti:
        if corrispondenze[i]:
            e = input("Indicare l'etichetta da associare all'argomento '" + i + "' (INVIO per '" + corrispondenze[i] + "'): ")
            if not e:
                print("Proposta confermata")
            elif e in etichette:
                corrispondenze[i] = e
            else:
                while bool(e in etichette) is False:
                    e = input("Etichetta non valida. Indicare l'etichetta da associare all'argomento '" + i + "': ")
                corrispondenze[i] = e
        else:
            e = input("Indicare l'etichetta da associare all'argomento '" + i + "': ")
            if e in etichette:
                corrispondenze[i] = e
            else:
                while bool(e in etichette) is False:
                    e = input("Etichetta non valida. Indicare l'etichetta da associare all'argomento '" + i + "': ")
                corrispondenze[i] = e
    return corrispondenze

def definisci_corrispondenze(funzione, etichette, corrispondenze_di_default):
    '''Guida l'utente nell'associare gli arogmenti richiesti  da una funzione alle etichette/colonne
    del file CSV dei dati. Se i valori di default sono congruenti propone di usare quelli.'''
    argomenti = recupera_argomenti(funzione)
    argomenti_di_default = list(corrispondenze_di_default.keys())
    etichette_di_default = list(corrispondenze_di_default.values())
    CORRISPONDENZE_DEFINITE = False
    while CORRISPONDENZE_DEFINITE is False:
        if (argomenti_di_default == argomenti and set(etichette_di_default) <= set(etichette)) is False:
            stampa("Corrispondenze argomenti-CSV assenti o non valide.")
            corrispondenze = mappa(argomenti, etichette)
        else:
            stampa("------------")
            stampa("Ho individuato le seguenti corrispondenze:")
            stampa(str(corrispondenze_di_default))
            stampa("------------")
            RISPOSTA_DATA = False
            while RISPOSTA_DATA is False:
                e = input("Confermi le corrispondenze (Sì/No)? ")
                if e in LISTA_OK:
                   stampa("Corrispondenze confermate.\n")
                   corrispondenze = corrispondenze_di_default
                   RISPOSTA_DATA = True
                elif e in LISTA_RISP:
                   stampa("Hai scelto di modificare le corrispondenze.")
                   corrispondenze = mappa(argomenti,ETICHETTE_CSV)
                   RISPOSTA_DATA = True
                else:
                   pass
        riga_di_esempio = DATI[0]
        parametri_di_esempio = {}
        for i in argomenti:
            parametri_di_esempio[i]=riga_di_esempio[corrispondenze[i]]
        stampa("------------")
        stampa("In base alle tue indicazioni, ho individuato le corrispondenze come nel seguente esempio:")
        logga(str(parametri_di_esempio))
        print(json.dumps(parametri_di_esempio, indent = 4))
        stampa("------------")
        body_di_esempio = funzione(**parametri_di_esempio)
        stampa("In base alle tue indicazioni, il messaggio risulta formato come segue:")
        logga(str(body_di_esempio))
        print(json.dumps(body_di_esempio, indent = 4))
        stampa("------------")
        RISPOSTA_DATA = False
        while RISPOSTA_DATA is False:
            approva = input("Confermi le tue scelte (Sì/No)? ")
            if approva in LISTA_OK:
                stampa("\nMessaggio di esempio approvato.\n")
                RISPOSTA_DATA = True
                CORRISPONDENZE_DEFINITE = True
            elif approva in LISTA_RISP:
                stampa("Messaggio di esempio non conforme alle aspettative. Ripeti la procedura.")
                RISPOSTA_DATA = True
            else:
                pass
    return corrispondenze

############################
#### CREAZIONE MESSAGGI ####
############################
def crea_body_scadenza_ci(data_scadenza_documento, codice_fiscale):
    '''Messaggio per avviso scadenza della carta di identità'''
    markdown = "Ti informiamo che **la tua carta di identità scade il giorno " + data_scadenza_documento + "**. "\
                "Puoi prenotare l'appuntamento per l'emissione di una nuova carta d'identità elettronica utlizzando "\
                "il servizio online [Prenota un appuntamento](" + URL_PRENOTAZIONE_CIE + ") "\
                "sul sito " + DELL_ENTE + "."
    body={}
    #body["time_to_live"] = 3600 #deprecato secondo la guida tecnica all'integrazione di IO v. 1.1. del 29/07/2021
    body["content"] = {"subject": "La tua carta di identità scade a breve", "markdown": markdown}
    body["fiscal_code"]=codice_fiscale
    return body
# Corrispondenze di default fra argomenti della funzione e CSV di input (se preso da un certo software)
CORRISPONDENZE_CI_DEFAULT = {"data_scadenza_documento":"dataScadenzaDocumento", "codice_fiscale":"codiceFiscale"}

def crea_body_scadenza_pec(nome, casella_pec, data_scadenza_pec, codice_fiscale):
    '''Messaggio per avviso scadneza/dismissione casella PEC'''
    markdown = "Ciao "+nome+ ",  \nTi informiamo che **la tua casella PEC " + casella_pec + " scade il giorno "\
                + data_scadenza_pec + "** e **non sarà più rinnovabile**, né dal Comune né da te.  \nTi invitiamo "\
                "pertanto a prendere nota della scadenza e **salvare per tempo i messaggi** presenti nella casella.  \n"\
                "Prossimamente " + L_ENTE + " riattiverà il servizio di assegnazione gratuita di una casella PEC "\
                "con un nuovo partner e modalità di rilascio più semplici.  \nTrovi maggiori informazioni sul sito "\
                "" + DELL_ENTE + "."
    body = {}
    #body["time_to_live"] = 3600 #deprecato
    body["content"] = {"subject": "Avviso sulla tua casella PEC offerta " + DALL_ENTE + "", "markdown": markdown, "due_date":data2(data_scadenza_pec)}
    body["fiscal_code"] = codice_fiscale
    return body
# Corrispondenze di default fra argomenti della funzione e CSV di input (se preso da un certo software)
CORRISPONDENZE_PEC_DEFAULT = {"nome":"Nome", "casella_pec":"Indirizzo", "data_scadenza_pec":"Fine competenze", "codice_fiscale":"Codice Fiscale"}

def crea_body_avviso_pagamento(codice_servizio_incasso, causale, importo, codice_avviso, scadenza, email, codice_fiscale):
    '''Contenuto di un messaggio per avviso di pagamento'''
    if codice_servizio_incasso in ELENCO_SERVIZI_INCASSO:
        nome_servizio = str(PAGOPA_CFG[codice_servizio_incasso]["nome"])
    else:
        nome_servizio = "---"
    markdown = "Ti informiamo che è stato emesso un avviso di pagamento a tuo nome per il servizio **" +nome_servizio+ \
        "**,  \n  \n" + "**Causale**: " + causale + "  \n  \n**Importo**: euro " + str(importo) + \
        "  \n  \nPuoi procedere al pagamento dell’avviso direttamente dalla app IO con l'apposito tasto.  \n  \n"\
        "In alternativa, puoi pagare o scaricare l’avviso in formato PDF per il pagamento sul territorio nella pagina "\
        "[Pagamenti Online](" + URL_PAGAMENTI + ") sul sito " + DELL_ENTE + ".  \n"\
        "Da lì potrai visualizzare anche lo storico dei tuoi pagamenti e prelevare le ricevute."
    payment_data={}
    payment_data["amount"] = int(float(importo)*100)
    payment_data["notice_number"] = str(codice_avviso)
    payment_data["invalid_after_due_date"] = False
    body={}
    #body["time_to_live"] = 3600    #deprecato
    body["content"] = {"subject":"Avviso di pagamento", "markdown":markdown,
                        "payment_data":payment_data, "due_date": str(data(scadenza))}
    body["fiscal_code"] = codice_fiscale
    return body
# Corrispondenze di default fra argomenti della funzione e CSV di input (se preso da un certo software)
CORRISPONDENZE_AP_DEFAULT = {'codice_servizio_incasso': 'identificativoServizio',
        'causale': 'causaleDebito', 'importo': 'Importo', 'codice_avviso': 'codiceAvviso', 'scadenza': 'dataScadenza',
        'email': 'e-mailPagatore', 'codice_fiscale': 'codiceidentificativoPagatore'}
        
def crea_body_sollecito_pagamento(codice_servizio_incasso, causale, importo, codice_avviso, scadenza, email, codice_fiscale):
    '''Contenuto di un messaggio per avviso di pagamento DI SOLLECITO'''
    if codice_servizio_incasso in ELENCO_SERVIZI_INCASSO:
        nome_servizio = str(PAGOPA_CFG[codice_servizio_incasso]["nome"])
    else:
        nome_servizio = "---"
    markdown = "Ti informiamo che non ci risulta pagato un avviso di pagamento a tuo nome per il servizio **" +nome_servizio+ \
        "**,  \n  \n" + "**Causale**: " + causale + "  \n  \n**Importo**: euro " + str(importo) + \
        "  \n  \nPuoi procedere al pagamento dell’avviso direttamente dalla app IO con l'apposito tasto.  \n  \n"\
        "In alternativa, puoi pagare o scaricare l’avviso in formato PDF per il pagamento sul territorio nella pagina "\
        "[Pagamenti Online](" + URL_PAGAMENTI + ") sul sito " + DELL_ENTE + ".  \n"\
        "Da lì potrai visualizzare anche lo storico dei tuoi pagamenti e prelevare le ricevute."
    payment_data={}
    payment_data["amount"] = int(float(importo)*100)
    payment_data["notice_number"] = str(codice_avviso)
    payment_data["invalid_after_due_date"] = False
    body={}
    #body["time_to_live"] = 3600    #deprecato
    body["content"] = {"subject":"Avviso di pagamento", "markdown":markdown,
                        "payment_data":payment_data, "due_date": str(data(scadenza))}
    body["fiscal_code"] = codice_fiscale
    return body
# Corrispondenze di default fra argomenti della funzione e CSV di input (se preso da un certo software)
CORRISPONDENZE_SOLL_DEFAULT = {'codice_servizio_incasso': 'identificativoServizio',
        'causale': 'causaleDebito', 'importo': 'Importo', 'codice_avviso': 'codiceAvviso', 'scadenza': 'dataScadenza',
        'email': 'e-mailPagatore', 'codice_fiscale': 'codiceidentificativoPagatore'}

### FUNZIONI ELEMENTARI PER INTERAZIONE CON LE API DI IO
def get_profile_post(codice_fiscale, servizio_io):
    apikey = ottieni_apikey(servizio_io)
    headers={"Ocp-Apim-Subscription-Key":apikey}
    with open(logFileName, "a+") as logFile:
        requestTime=timestamp()
        logRequest(logFile, requestTime, "GET", "profiles", codice_fiscale)
        r = requests.post(BASE_URL_IO+"/profiles", headers = headers, timeout=100, json={"fiscal_code" : codice_fiscale})
        responseTime=timestamp()
        info = str(r.json()["sender_allowed"]) if r.status_code==200 else str(r.json()["title"])
        logResponse(logFile, responseTime, requestTime, r.status_code, info)
        return r

def submit_message(codice_fiscale, servizio_io, body): #CF nel payload
    apikey = ottieni_apikey(servizio_io)
    headers={"Ocp-Apim-Subscription-Key":apikey,
                "Content-Type":"application/json", "Connection":"keep-alive"}
    with open(logFileName, "a+") as logFile:
        requestTime=timestamp()
        logRequest(logFile, requestTime, "POST", "submit_message", codice_fiscale)
        r = requests.post(BASE_URL_IO+"/messages", headers = headers, timeout=100, json=body)
        responseTime=timestamp()
        info = str(r.json()["id"]) if r.status_code==201 else str(r.json()["title"])
        logResponse(logFile, responseTime, requestTime, r.status_code, info)
        return r

def get_message(codice_fiscale, message_id, servizio_io):
    apikey = ottieni_apikey(servizio_io)
    headers={"Ocp-Apim-Subscription-Key": apikey}
    with open(logFileName, "a+") as logFile:
        requestTime=timestamp()
        logRequest(logFile, requestTime, "GET", "get_message", message_id)
        r = requests.get(BASE_URL_IO+"/messages/"+codice_fiscale+"/"+message_id, headers=headers, timeout=100)
        responseTime=timestamp()
        info = str(r.json()["status"]) if r.status_code==200 else str(r.json()["title"])
        logResponse(logFile, responseTime, requestTime, r.status_code, info)
        return r


#### FUNZIONI ARTICOLATE PER INTERAZIONE CON IO
    
def invia_lotto(lotto, lotto_json):
    '''Invia un lotto tramite submit_message'''
    t = 0 #pausa iniziale fra due iterazioni
    tmax = 0.3 #limite massimo della pausa (se superato si abbandona)
    passo = 0.1 #incremento della pausa fra due iterazioni a ogni errore
    pausa = 3 #pausa una tantum in seguito a errore per server sovraccarico
    dati_in_coda = [] #lista vuoto per raccogliere la coda di tabellaDati eventualmente non elaborata
    TOTALE = len(lotto)
    statistiche = ""
    cf_errati = []
    if TOTALE == 0:
        print("Niente da inviare.")
        statistiche = "Niente da inviare."
    else:
        for dizio in lotto:
            dizio.update({"inizio_processo":timestamp()})
            cf_verificato = False
            while cf_verificato is False:
                if t > tmax:
                    print("Il sistema è sovraccarico, interrompo l'interrogazione.")
                    salva_dizionario(lotto, lotto_json)
                    statistiche = "Invio del lotto interrotto per sovraccarico. Recuperalo in seguito con la funzione R."
                    return statistiche, cf_errati
                else:
                    time.sleep(t)
                    if "status_iscrizione" in dizio:
                        cf_verificato = True
                    else:
                        try:
                            dizio.update({"timestamp_iscrizione":timestamp()})
                            iscrizione = get_profile_post(dizio.get("codice_fiscale"), dizio.get("servizio_io"))
                            dizio.update({"status_iscrizione":iscrizione.status_code})
                        except:
                            stampa(f"Qualcosa è andato storto. Puoi recuperare gli invii non fatti con l'apposita funzione.")
                            salva_dizionario(lotto, lotto_json)
                            break
                        if iscrizione.status_code == 200:
                            dizio.update({"stato_iscrizione":"Presente su IO"})
                            dizio.update({"sender_allowed":iscrizione.json().get("sender_allowed")})
                            cf_verificato = True
                        elif iscrizione.status_code == 400:
                            dizio.update({"stato_iscrizione":"Errore"})
                            dizio.update({"detail_iscrizione":iscrizione.json().get("detail")})
                            cf_verificato = True
                        elif iscrizione.status_code == 404:
                            dizio.update({"stato_iscrizione":"Non su IO"})
                            cf_verificato = True
                        elif iscrizione.status_code in [401, 403]:
                            cf_verificato = True
                        elif iscrizione.status_code == 429:
                            stampa(f"Server sovraccarico, attendo {str(pausa)} secondi.")
                            t = t + passo
                            time.sleep(pausa)
                        else:
                            pass
            messaggio_processato = False
            while messaggio_processato is False:
                if t > tmax:
                    print("Il sistema è sovraccarico, interrompo l'interrogazione.")
                    salva_dizionario(lotto, lotto_json)
                    statistiche = "Invio del lotto interrotto per sovraccarico. Recuperalo in seguito con la funzione R."
                    return statistiche, cf_errati
                else:
                    time.sleep(t)
                    if (dizio.get("status_iscrizione") == 200 and dizio.get("sender_allowed") is True):
                        if dizio.get("status_invio") in [201, 400, 500, 401, 403]:
                            print("Messaggio", str(LOTTO.index(dizio)+1), "già processato.")
                            messaggio_processato = True
                        else:
                            try:
                                dizio.update({"timestamp_invio":timestamp()})
                                response = submit_message(dizio.get("codice_fiscale"), dizio.get("servizio_io"), dizio.get("body"))
                                dizio.update({"status_invio":response.status_code})
                            except:
                                stampa(f"Qualcosa è andato storto. Puoi recuperare gli invii non fatti con l'apposita funzione.")
                                salva_dizionario(lotto, lotto_json)
                                break
                            if response.status_code == 201:
                                dizio.update({"id":response.json().get("id")})
                                messaggio_processato = True
                            elif response.status_code in [400, 500]:
                                dizio.update({"detail":response.json().get("detail")})
                                messaggio_processato = True                                
                            elif response.status_code in [401, 403]:
                                messaggio_processato = True
                            elif response.status_code == 429:
                                stampa(f"Server sovraccarico, attendo {str(pausa)} secondi.")
                                t = t + passo
                                time.sleep(pausa)
                            print("Invio", str(LOTTO.index(dizio)+1), "di", TOTALE,":", dizio.get("status_iscrizione"), dizio.get("sender_allowed"), dizio.get("status_invio"))
                    else:
                        messaggio_processato = True
                        print("Invio", str(LOTTO.index(dizio)+1), "di", TOTALE,":", dizio.get("status_iscrizione"), dizio.get("sender_allowed"), dizio.get("status_invio"))
        salva_dizionario(lotto, lotto_json)
        NON_ISCRITTI = sum([1 for d in lotto if d.get("sender_allowed") is False])
        SENZA_IO = sum([1 for d in lotto if d.get("status_iscrizione") == 404])
        ACCETTATI = sum([1 for d in lotto if d.get("id") != None])
        IN_ERRORE = sum([1 for d in lotto if d.get("detail") != None])
        CF_IN_ERRORE = sum([1 for d in lotto if d.get("status_iscrizione") in [400, 401, 403]])
        if CF_IN_ERRORE > 0:
            for d in lotto:
                if d.get("status_iscrizione") in [400, 401, 403]:
                    cf_errati.append(d.get("codice_fiscale"))
        statistiche = f"\nMessaggi totali: {TOTALE}"\
                      f"\nMessaggi verso c.f. non iscritti: {NON_ISCRITTI}"\
                      f"\nMessaggi verso c.f. privi di app IO: {SENZA_IO}"\
                      f"\nMessaggi verso c.f. in errore: {CF_IN_ERRORE}"\
                      f"\nMessaggi in errore: {IN_ERRORE}"\
                      f"\nMessaggi accettati: {ACCETTATI}\n"
    return statistiche, cf_errati

def controlla_cf(lista_cf, servizio_io):
    ''' Funzione per controllare iscrizione di una lista di CF a un servizio'''
    t = 0 #pausa iniziale fra due iterazioni
    tmax = 0.3 #limite massimo della pausa fra due iterazioni superato il quale si abbandona l'interrogazione
    passo = 0.1 #incremento della pausa fra due iterazioni a ogni errore
    pausa = 3 #pausa una tantum in seguito a errore per server sovraccarico 
    utentiIscritti=[]
    utentiNonIscritti=[]
    utentiSenzaAppIO=[]
    interrogazioniInErrore=[]
    interrogazioniNonAutorizzate=[]
    interrogazioniInCoda = lista_cf
    contatore=1
    totale=len(lista_cf)
    try:
        for cf in lista_cf:
            inviato = False
            while not inviato:
                if t > tmax:
                    print("Il sistema è sovraccarico, interrompo l'interrogazione.")
                    interrogazioniInCoda = lista_cf[lista_cf.index(cf):]
                    return ({"iscritti":utentiIscritti, "nonIscritti":utentiNonIscritti, "senzaAppIO":utentiSenzaAppIO, "inErrore":interrogazioniInErrore}, interrogazioniInCoda)
                else:
                    time.sleep(t)
                    print(contatore,"di",totale)
                    risposta = get_profile_post(cf, servizio_io)
                    if risposta.status_code == 200:
                        if risposta.json()["sender_allowed"]:
                            utentiIscritti.append(cf)
                        else:
                            utentiNonIscritti.append(cf)
                        inviato =  True
                        contatore += 1
                    elif risposta.status_code == 429:
                        print("Il server IO è sovraccarico, attendo e inserisco una pausa fra le prossime richieste.")
                        t += passo
                        time.sleep(pausa)
                    else:
                        if risposta.status_code == 404:
                            utentiSenzaAppIO.append(cf)
                        elif risposta.status_code == 401:
                            interrogazioniInErrore.append(cf)
                        else: ##status_code 403 unauthorized
                            interrogazioniNonAutorizzate.append(cf)
                        inviato = True
                        contatore += 1
        interrogazioniInCoda = lista_cf[lista_cf.index(cf)+1:]
    except:
        print("Qualcosa è andato storto. Guarda la coda.")
    return ({"iscritti":utentiIscritti, "nonIscritti":utentiNonIscritti, "senzaAppIO":utentiSenzaAppIO, "inErrore":interrogazioniInErrore, "nonAutorizzate":interrogazioniNonAutorizzate}, interrogazioniInCoda)

#####################################
### INSTALLAZIONE AL PRIMO AVVIO ####
#####################################
print("                                    #####                ### ####### \n"\
        "#####    ##   #####  #        ##   #     #  ####  #    #  #  #     # \n"\
        "#    #  #  #  #    # #       #  #  #       #    # ##   #  #  #     # \n"\
        "#    # #    # #    # #      #    # #       #    # # #  #  #  #     # \n"\
        "#####  ###### #####  #      ###### #       #    # #  # #  #  #     # \n"\
        "#      #    # #   #  #      #    # #     # #    # #   ##  #  #     # \n"\
        "#      #    # #    # ###### #    #  #####   ####  #    # ### ####### \n")
print("Ciao "+CALLING_USER+".")
if os.path.exists("lotti/") is False:
    os.mkdir("./lotti/")
if ((os.path.exists("IO.cfg")) and (os.path.exists("pagoPA.cfg"))) is False:
    print("Il programma non è configurato.")
    print("Copia i file di configurazione .master.cfg nella cartella di questo programma.")
    print("Ti chiederò di: ")
    print("- scegliere una password")
    CHIAVE = imposta_password()
    print("Password impostata. \nAnnotala in un luogo segreto e sicuro: "\
          "NON potrai recuperarla in alcun modo.")
    print("Importiamo la configurazione di IO dal file IO.master.cfg.\n\
           Se non lo trovi chiedi a chi ti ha procurato il programma.")
    passwM = pwinput.pwinput(prompt = "Inserici la password dei file .master.cfg: ")
    passwordM = passwM.encode()
    CHIAVEM = base64.urlsafe_b64encode(kdf().derive(passwordM))
    passwM = ""
    passwordM = b""
    PASSWORDM_CORRETTA = False
    while PASSWORDM_CORRETTA is False:
        try:
            ricifra_file("IO.master.cfg", CHIAVEM, CHIAVE, "IO.cfg")
            print("Configurazione di IO importata.")
            PASSWORDM_CORRETTA = True
        except:
                print("La password NON è corretta.")
                passwM = pwinput.pwinput()
                passwordM = passwM.encode()
                CHIAVEM = base64.urlsafe_b64encode(kdf().derive(passwordM))
                passwM = ""
                passwordM = b""
    ricifra_file("pagoPA.master.cfg", CHIAVEM, CHIAVE, "pagoPA.cfg")
    ricifra_file("permessi.master.cfg", CHIAVEM, CHIAVE, "permessi.cfg")
    print("Configurazione di pagoPA importata.")
    print("\nRicorda la password per avviare nuovamente questo programma.")
    print("Se non ricordi la password cancella il file IO.cfg e ripeti la configurazione.")

#####################################
###     AVVIO SUCCESSIVO        #####
#####################################
if "CHIAVE" in locals(): #si realizza immediatamente dopo la configurazione
    print("\nSei già loggato. Proseguiamo.")
else:
    PASSWORD_CORRETTA = False
    while PASSWORD_CORRETTA is False:
        passw = pwinput.pwinput()
        password = passw.encode()
        CHIAVE = base64.urlsafe_b64encode(kdf().derive(password))
        passw = ""
        password = b""
        with open("pagoPA.cfg", "r") as f:
            try:
                PAGOPA_CFG = decifra_dizionario("pagoPA.cfg", CHIAVE)
                print("La password è corretta.")
                PASSWORD_CORRETTA = True
                PAGOPA_CFG = {}
            except:
                print("La password NON è corretta.\n")
                
CONTINUARE = True
while CONTINUARE is True:

    ###Scegli la funzione da usare
    print("\nparlaConIO consente le seguenti funzioni:\n\n"\
          "1 - invio lotto di avvisi di pagamento;\n"\
          "2 - invio lotto di messaggi per scadenza della carta d'identità;\n"\
          "3 - invio lotto di messaggi per scadenza PEC;\n"\
          "4 - invio lotto di solleciti di pagamento;\n"\
          "5 - verifica la diffusione di IO;\n"
          "6 - verifica la diffusione di IO per nucleo familiare;\n"
          "R - recupera un precedente invio;\n"\
          "C - configurazione di parlaConIO;\n"\
          "U - esci da parlaConIO.\n")
    PERMESSI = decifra_dizionario("permessi.cfg", CHIAVE).get("PERMESSI")
    SERVIZI_IO = {}
    for i in decifra_dizionario("IO.cfg", CHIAVE):
        SERVIZI_IO.update({i:decifra_dizionario("IO.cfg", CHIAVE)[i]["nome"]})
    PERMESSI_IO = decifra_dizionario("permessi.cfg", CHIAVE).get("PERMESSI_IO")
    SCELTE = ["1", "2", "3", "4", "5", "6", "C", "c", "U", "u", "R", "r"]
    scelta = input("Cosa vuoi fare? Scegli 1, 2, 3, 4, 5, 6, R o C (U per uscire): ")
    while scelta not in PERMESSI:
        if scelta not in SCELTE:
            scelta = input("Scelta non valida. Scegli 1, 2, 3, 4, 5, 6, R o C (U per uscire): ")
        elif scelta not in PERMESSI:
            scelta = input("Funzione non abilitata. Scegli 1, 2, 3, 4, 5, 6, R o C (U per uscire): ")
    if scelta in ["U", "u"]:
        print("\nCiao " + CALLING_USER + ", è stato un piacere fare affari con te ;)")
        termina()
    
#############################
######  LOTTO AVVISI PAG.   #
#############################
    elif scelta == "1":
        print("\n"+scelta + " Invio lotto di avvisi di pagamento\n")
        print("Per questa operazione hai bisogno di un file CSV, "\
              "delimitato da \";\", con i dati dei pagamenti.")
        print("Copialo nella cartella del programma, per tua facilità.\n")
        ref = input("Per iniziare, indica una breve descrizione della spedizione: ")    
# Importo i dati dei servizi di pagamento
        PAGOPA_CFG = decifra_dizionario("pagoPA.cfg", CHIAVE)
        ELENCO_SERVIZI_INCASSO = list(PAGOPA_CFG.keys())
# Individuo il file CSV con i dati in input
        NOME_FILE_DATI = chiedi_nome_file_dati()
# Inizializzo la cartella di lotto e i file di output e log
        DATA_LOTTO = timestamp_breve()
        PATH = crea_cartella(ref, DATA_LOTTO) # crea la cartella di lavoro del lotto
        LOTTO_LOG = PATH + DATA_LOTTO + "-" + "lotto.log"
        DATI_JSON = PATH + DATA_LOTTO + "-" + "dati.json"
        RICEVUTA_JSON = PATH + DATA_LOTTO + "-" + "ricevuta.json"
        LOTTO_JSON=PATH + DATA_LOTTO + "-" + "lotto.json"
        REQUESTS_LOG = PATH + DATA_LOTTO + "-" + "requests.log"
        fh = logging.FileHandler(REQUESTS_LOG)
        log.addHandler(fh)
        logga("Ciao " + CALLING_USER + "!") #apre il lotto di log salutando l'utente
        stampa("Ho creato la cartella di lotto: "+PATH)
        logga("Data della richiesta: "+DATA_LOTTO)
        logga("Motivo della richiesta: "+ref)
# Creo ricevuta per successivi recuperi/verifiche
        ricevuta={}
        ricevuta["nomeFileDati"] = NOME_FILE_DATI
        ricevuta["cartellaDiLavoro"] = PATH
        ricevuta["utente"] = CALLING_USER
        ricevuta["data_lotto"] = DATA_LOTTO
        ricevuta["lotto_json"] = LOTTO_JSON
        ricevuta["lotto_log"] = LOTTO_LOG
        salva_dizionario(ricevuta, RICEVUTA_JSON)
## Estraggo il file CSV e creo un array di dizionari e un file json nella cartella di lotto
        DATI, ETICHETTE_CSV = importa_dati_csv(NOME_FILE_DATI, DATI_JSON)
## Definisco le corrispondenze fra colonne del CSV e argomenti della funzione
        corrispondenze = definisci_corrispondenze(crea_body_avviso_pagamento, ETICHETTE_CSV, CORRISPONDENZE_AP_DEFAULT)
## Creo dizionario LOTTO e file -lotto.json
        LOTTO = []
        argomenti = recupera_argomenti(crea_body_avviso_pagamento)
        for dato in DATI:
            dizio = {}
            dizio["codice_fiscale"] = dato[corrispondenze["codice_fiscale"]]
            if "servizioIO" in PAGOPA_CFG[dato["identificativoServizio"]]:
                dizio["servizio_io"] = PAGOPA_CFG[dato["identificativoServizio"]]["servizioIO"]
            else:
                dizio["servizio_io"] = "AP" ##METTERE QUI IL CODICE DI UN SERVIZIO IO DA USARE GENERICAMENTE
            parametri = {}
            for i in argomenti:
                parametri[i] = dato[corrispondenze[i]]
            dizio["body"] = crea_body_avviso_pagamento(**parametri)
            LOTTO.append(dizio)
        salva_dizionario(LOTTO, LOTTO_JSON)
## Invio il lotto
        statistiche, CF_ERRATI = invia_lotto(LOTTO, LOTTO_JSON)
        stampa("\nElaborazione degli invii terminata.")
        stampa(f"Consulta il file {LOTTO_JSON} per dettagli.")
        stampa(statistiche)
        if len(CF_ERRATI) > 0:
            stampa("----> ATTENZIONE! Ci sono dei codici fiscali apparentemente errati:")
            stampa("----> Verificali: " + str(CF_ERRATI))
        stampa("\nPuoi usare la funzione R di parlaConIO per ritentare invii in errore.")

#############################
###### LOTTO SCADENZA C.I. ##
############################# 
    elif scelta == "2":
        print("\n" + scelta + " - Invio lotto di avvisi di scadenza della carta d'identità")    
        print("Per questa operazione hai bisogno di un file CSV, "\
              "delimitato da \";\", con almeno la data di scadenza della carta d'identità e "\
              "il codice fiscale del suo titolare.")
        print("Copialo nella cartella del programma, per tua facilità.\n")
        ref = input("Per iniziare, indica una breve descrizione della spedizione: ")    
# Individuo il file CSV con i dati in input
        NOME_FILE_DATI = chiedi_nome_file_dati()
# Inizializzo la cartella di lotto e i file di output e log
        DATA_LOTTO = timestamp_breve()
        PATH = crea_cartella(ref, DATA_LOTTO) # crea la cartella di lavoro del lotto
        LOTTO_LOG = PATH + DATA_LOTTO + "-" + "lotto.log"
        DATI_JSON = PATH + DATA_LOTTO + "-" + "dati.json"
        RICEVUTA_JSON = PATH + DATA_LOTTO + "-" + "ricevuta.json"
        LOTTO_JSON=PATH + DATA_LOTTO + "-" + "lotto.json"
        REQUESTS_LOG = PATH + DATA_LOTTO + "-" + "requests.log"
        fh = logging.FileHandler(REQUESTS_LOG)
        log.addHandler(fh)
        logga("Ciao " + CALLING_USER + "!") #apre il lotto di log salutando l'utente
        stampa("Ho creato la cartella di lotto: "+PATH)
        logga("Data della richiesta: "+DATA_LOTTO)
        logga("Motivo della richiesta: "+ref)
# Creo ricevuta per successivi recuperi/verifiche
        ricevuta={}
        ricevuta["nomeFileDati"] = NOME_FILE_DATI
        ricevuta["cartellaDiLavoro"] = PATH
        ricevuta["utente"] = CALLING_USER
        ricevuta["data_lotto"] = DATA_LOTTO
        ricevuta["lotto_json"] = LOTTO_JSON
        ricevuta["lotto_log"] = LOTTO_LOG
        salva_dizionario(ricevuta, RICEVUTA_JSON)
## Estraggo il file CSV e creo un array di dizionari e un file json nella cartella di lotto
        DATI, ETICHETTE_CSV = importa_dati_csv(NOME_FILE_DATI, DATI_JSON)
## Definisco le corrispondenze fra colonne del CSV e argomenti della funzione
        corrispondenze = definisci_corrispondenze(crea_body_scadenza_ci, ETICHETTE_CSV, CORRISPONDENZE_CI_DEFAULT)
## Creo dizionario LOTTO e file -lotto.json
        LOTTO = []
        argomenti = recupera_argomenti(crea_body_scadenza_ci)
        for dato in DATI:
            dizio = {}
            dizio["codice_fiscale"] = dato[corrispondenze["codice_fiscale"]]
            dizio["servizio_io"] = "SCI" ##USARE IL CODICE DEL SERVIZIO IO IN USO
            parametri = {}
            for i in argomenti:
                parametri[i] = dato[corrispondenze[i]]
            dizio["body"] = crea_body_scadenza_ci(**parametri)
            LOTTO.append(dizio)
        salva_dizionario(LOTTO, LOTTO_JSON)
## Invio il lotto
        statistiche, CF_ERRATI = invia_lotto(LOTTO, LOTTO_JSON)
        stampa("\nElaborazione degli invii terminata.")
        stampa(f"Consulta il file {LOTTO_JSON} per dettagli.")
        stampa(statistiche)
        if len(CF_ERRATI) > 0:
            stampa("----> ATTENZIONE! Ci sono dei codici fiscali apparentemente errati:")
            stampa("----> Verificali: " + str(CF_ERRATI))
        stampa("\nPuoi usare la funzione R di parlaConIO per ritentare invii in errore.")
       
#############################
###### LOTTO SCADENZA PEC  ##
#############################
    elif scelta == "3":
        print("\n" + scelta + " - Invio lotto di avvisi di scadenza della PEC")
        print("Per questa operazione hai bisogno di un file CSV, "\
              "delimitato da \";\", con almeno la data di scadenza della casella PEC, "\
              "il codice fiscale e il nome del suo titolare e l'indirizzo della casella.")
        print("Copialo nella cartella del programma, per tua facilità.\n")
        ref = input("Per iniziare, indica una breve descrizione della spedizione: ")    
# Individuo il file CSV con i dati in input
        NOME_FILE_DATI = chiedi_nome_file_dati()
# Inizializzo la cartella di lotto e i file di output e log
        DATA_LOTTO = timestamp_breve()
        PATH = crea_cartella(ref, DATA_LOTTO) # crea la cartella di lavoro del lotto
        LOTTO_LOG = PATH + DATA_LOTTO + "-" + "lotto.log"
        DATI_JSON = PATH + DATA_LOTTO + "-" + "dati.json"
        RICEVUTA_JSON = PATH + DATA_LOTTO + "-" + "ricevuta.json"
        LOTTO_JSON=PATH + DATA_LOTTO + "-" + "lotto.json"
        REQUESTS_LOG = PATH + DATA_LOTTO + "-" + "requests.log"
        fh = logging.FileHandler(REQUESTS_LOG)
        log.addHandler(fh)
        logga("Ciao " + CALLING_USER + "!") #apre il lotto di log salutando l'utente
        stampa("Ho creato la cartella di lotto: "+PATH)
        logga("Data della richiesta: "+DATA_LOTTO)
        logga("Motivo della richiesta: "+ref)
# Creo ricevuta per successivi recuperi/verifiche
        ricevuta={}
        ricevuta["nomeFileDati"] = NOME_FILE_DATI
        ricevuta["cartellaDiLavoro"] = PATH
        ricevuta["utente"] = CALLING_USER
        ricevuta["data_lotto"] = DATA_LOTTO
        ricevuta["lotto_json"] = LOTTO_JSON
        ricevuta["lotto_log"] = LOTTO_LOG
        salva_dizionario(ricevuta, RICEVUTA_JSON)
## Estraggo il file CSV e creo un array di dizionari e un file json nella cartella di lotto
        DATI, ETICHETTE_CSV = importa_dati_csv(NOME_FILE_DATI, DATI_JSON)
## Definisco le corrispondenze fra colonne del CSV e argomenti della funzione
        corrispondenze = definisci_corrispondenze(crea_body_scadenza_pec, ETICHETTE_CSV, CORRISPONDENZE_PEC_DEFAULT)
## Creo dizionario LOTTO e file -lotto.json
        LOTTO = []
        argomenti = recupera_argomenti(crea_body_scadenza_pec)
        for dato in DATI:
            dizio = {}
            dizio["codice_fiscale"] = dato[corrispondenze["codice_fiscale"]]
            dizio["servizio_io"] = "COM" ##USARE IL CODICE DEL SERVIZIO IO IN USO
            parametri = {}
            for i in argomenti:
                parametri[i] = dato[corrispondenze[i]]
            dizio["body"] = crea_body_scadenza_pec(**parametri)
            LOTTO.append(dizio)
        salva_dizionario(LOTTO, LOTTO_JSON)
## Invio il lotto
        statistiche, CF_ERRATI = invia_lotto(LOTTO, LOTTO_JSON)
        stampa("\nElaborazione degli invii terminata.")
        stampa(f"Consulta il file {LOTTO_JSON} per dettagli.")
        stampa(statistiche)
        if len(CF_ERRATI) > 0:
            stampa("----> ATTENZIONE! Ci sono dei codici fiscali apparentemente errati:")
            stampa("----> Verificali: " + str(CF_ERRATI))
        stampa("\nPuoi usare la funzione R di parlaConIO per ritentare invii in errore.")

#############################
###### SOLLECITI DI PAGAM.###
#############################
    elif scelta == "4":
        print("\n" + scelta + " - Invio lotto di solleciti di pagamento")
        print("Per questa operazione hai bisogno di un file CSV, "\
              "delimitato da \";\", con i dati dei pagamenti.")
        print("Copialo nella cartella del programma, per tua facilità.\n")
        ref = input("Per iniziare, indica una breve descrizione della spedizione: ")    
# Importo i dati dei servizi di pagamento
        PAGOPA_CFG = decifra_dizionario("pagoPA.cfg", CHIAVE)
        ELENCO_SERVIZI_INCASSO = list(PAGOPA_CFG.keys())
# Individuo il file CSV con i dati in input
        NOME_FILE_DATI = chiedi_nome_file_dati()
# Inizializzo la cartella di lotto e i file di output e log
        DATA_LOTTO = timestamp_breve()
        PATH = crea_cartella(ref, DATA_LOTTO) # crea la cartella di lavoro del lotto
        LOTTO_LOG = PATH + DATA_LOTTO + "-" + "lotto.log"
        DATI_JSON = PATH + DATA_LOTTO + "-" + "dati.json"
        RICEVUTA_JSON = PATH + DATA_LOTTO + "-" + "ricevuta.json"
        LOTTO_JSON=PATH + DATA_LOTTO + "-" + "lotto.json"
        REQUESTS_LOG = PATH + DATA_LOTTO + "-" + "requests.log"
        fh = logging.FileHandler(REQUESTS_LOG)
        log.addHandler(fh)
        logga("Ciao " + CALLING_USER + "!") #apre il lotto di log salutando l'utente
        stampa("Ho creato la cartella di lotto: "+PATH)
        logga("Data della richiesta: "+DATA_LOTTO)
        logga("Motivo della richiesta: "+ref)
# Creo ricevuta per successivi recuperi/verifiche
        ricevuta={}
        ricevuta["nomeFileDati"] = NOME_FILE_DATI
        ricevuta["cartellaDiLavoro"] = PATH
        ricevuta["utente"] = CALLING_USER
        ricevuta["data_lotto"] = DATA_LOTTO
        ricevuta["lotto_json"] = LOTTO_JSON
        ricevuta["lotto_log"] = LOTTO_LOG
        salva_dizionario(ricevuta, RICEVUTA_JSON)
## Estraggo il file CSV e creo un array di dizionari e un file json nella cartella di lotto
        DATI, ETICHETTE_CSV = importa_dati_csv(NOME_FILE_DATI, DATI_JSON)
## Definisco le corrispondenze fra colonne del CSV e argomenti della funzione
        corrispondenze = definisci_corrispondenze(crea_body_sollecito_pagamento, ETICHETTE_CSV, CORRISPONDENZE_SOLL_DEFAULT)
## Creo dizionario LOTTO e file -lotto.json
        LOTTO = []
        argomenti = recupera_argomenti(crea_body_sollecito_pagamento)
        for dato in DATI:
            dizio = {}
            dizio["codice_fiscale"] = dato[corrispondenze["codice_fiscale"]]
            if "servizioIO" in PAGOPA_CFG[dato["identificativoServizio"]]:
                dizio["servizio_io"] = PAGOPA_CFG[dato["identificativoServizio"]]["servizioIO"]
            else:
                dizio["servizio_io"] = "AP" ##METTERE QUI IL CODICE DI UN SERVIZIO IO DA USARE GENERICAMENTE
            parametri = {}
            for i in argomenti:
                parametri[i] = dato[corrispondenze[i]]
            dizio["body"] = crea_body_sollecito_pagamento(**parametri)
            LOTTO.append(dizio)
        salva_dizionario(LOTTO, LOTTO_JSON)
## Invio il lotto
        statistiche, CF_ERRATI = invia_lotto(LOTTO, LOTTO_JSON)
        stampa("\nElaborazione degli invii terminata.")
        stampa(f"Consulta il file {LOTTO_JSON} per dettagli.")
        stampa(statistiche)
        if len(CF_ERRATI) > 0:
            stampa("----> ATTENZIONE! Ci sono dei codici fiscali apparentemente errati:")
            stampa("----> Verificali: " + str(CF_ERRATI))
        stampa("\nPuoi usare la funzione R di parlaConIO per ritentare invii in errore.")

#############################
###### VERIFICA DIFFUSIONE  #
#############################     
    elif scelta == "5":
        print("\n" + scelta + " - Verifica la diffusione di IO")
        print("\nHai bisogno di caricare un file CSV in cui una colonna contiene i codici fiscali da verificare")
        ref = input("Per iniziare, indica una breve descrizione della verifica: ")    
# Inizializzo la cartella di lotto e i file di output e log
        DATA_LOTTO = timestamp_breve()
        PATH = crea_cartella("VerificaCF - " + ref, DATA_LOTTO) # crea la cartella di lavoro del lotto
        LOTTO_LOG = PATH + DATA_LOTTO + "-" + "lotto.log"
        DATI_JSON = PATH + DATA_LOTTO + "-" + "dati.json"
        RICEVUTA_JSON = PATH + DATA_LOTTO + "-" + "ricevuta.json"
        LOTTO_JSON=PATH + DATA_LOTTO + "-" + "lotto.json"
        REQUESTS_LOG = PATH + DATA_LOTTO + "-" + "requests.log"
        fh = logging.FileHandler(REQUESTS_LOG)
        log.addHandler(fh)
        logga("Ciao " + CALLING_USER + "!") #apre il lotto di log salutando l'utente
        stampa("Ho creato la cartella di lotto: "+PATH)
        logga("Data della richiesta: "+DATA_LOTTO)
        logga("Motivo della richiesta: "+ref)
# Individuo il file CSV con i dati in input
        NOME_FILE_DATI = chiedi_nome_file_dati()
        DATI, ETICHETTE_CSV = importa_dati_csv(NOME_FILE_DATI, DATI_JSON)
# Creo ricevuta per successivi recuperi/verifiche
        ricevuta={}
        ricevuta["nomeFileDati"] = NOME_FILE_DATI
        ricevuta["cartellaDiLavoro"] = PATH
        ricevuta["utente"] = CALLING_USER
        ricevuta["data_lotto"] = DATA_LOTTO
        ricevuta["lotto_json"] = LOTTO_JSON
        ricevuta["lotto_log"] = LOTTO_LOG
        salva_dizionario(ricevuta, RICEVUTA_JSON)
## Definisco le corrispondenze fra colonne del CSV e argomenti della funzione
        print("\nIl CSV importato ha le seguenti colonne:")
        for etichetta in ETICHETTE_CSV:
            print(etichetta)
        CHIAVE_CF = input("Indicare l'etichetta del codice fiscale: ")
        while CHIAVE_CF not in ETICHETTE_CSV:
            CHIAVE_CF = input("Etichetta non valida. Indicare l'etichetta del codice fiscale: ")
# Elimino i codici fiscali ripetuti
        LISTA_CF = []
        for dato in DATI:
            LISTA_CF.append(dato.get(CHIAVE_CF))
# Seleziono il servizio IO per cui verificare l'iscrizione
        print("Elenco dei servizi IO disponibili: ")
        for i in PERMESSI_IO:  ###qui poi sostituire con PERMESSI_IO
            print(i, ":", SERVIZI_IO.get(i))
        servizio_io = input("Per quale servizio verificare l'iscrizione? ")
        while servizio_io not in PERMESSI_IO:
            servizio_io = input("Servizio non valido. Indicare il servizio: ")
# lancio la verifica
        LOTTO, CODA = controlla_cf(LISTA_CF, servizio_io)
        salva_dizionario(LOTTO, LOTTO_JSON)
# Resituisco risultati
# LOTTO = {"iscritti":utentiIscritti, "nonIscritti":utentiNonIscritti, "senzaAppIO":utentiSenzaAppIO, "inErrore":interrogazioniInErrore}
        stampa("Risultati:")
        stampa("- Codici fiscali verificati: " +str(len(LISTA_CF)))
        stampa("- Iscritti: " + str(len(LOTTO["iscritti"])))
        stampa("- Non iscritti: " + str(len(LOTTO["nonIscritti"])))
        stampa("- Senza app IO: " + str(len(LOTTO["senzaAppIO"])))
        stampa("- In errore: " + str(len(LOTTO["inErrore"])))
        stampa("- Richieste non autorizzate: "+ str(len(LOTTO["nonAutorizzate"])))
        if len(LOTTO["nonAutorizzate"]) > 0:
            stampa("----> ATTENZIONE! Ci sono delle interrogazioni respinte:")
            stampa("----> Verificale: " + str(LOTTO["nonAutorizzate"]))
            stampa("Probabilmente sei collegato da una postazione non autorizzata.")
        if len(LOTTO["inErrore"]) > 0:
            stampa("----> ATTENZIONE! Ci sono dei codici fiscali apparentemente errati:")
            stampa("----> Verificali: " + str(LOTTO["inErrore"]))
        if len(CODA) > 0:
            stampa("----> ATTENZIONE! Ci sono dei codici fiscali non processati per interruzione:")
            stampa("----> Verificali: " + str(CODA))

#######################################
###### VERIFICA DIFFUSIONE PER NUCLEI #
#######################################     
    elif scelta == "6":
        print("\n" + scelta + " - Verifica la diffusione di IO per nuclei familiari")
        print("\nHai bisogno di caricare un file CSV in cui una colonna contiene "\
                "i codici fiscali da verificare e il codice del nucleo")
        ref = input("Per iniziare, indica una breve descrizione della verifica: ")
        print("Grazie " + CALLING_USER +", a breve completeremo anche questa funzione.")

#############################
###### RECUPERA INVIO PREC.##
#############################
    elif scelta in ["R", "r"]:
        print("\n" + scelta + " - Recupero di un precedente invio.")
        print("\nHai bisogno di una ricevuta in formato json di un precedente invio.")
        print("Puoi sceglierla da un elenco oppure indicare il file manualmente.")
        print("Ti conviene copiarla dalla cartella di lotto alla cartella di questo programma e rinominarla.")
        RICEVUTE = []
        for cartella, sottocartelle, files in os.walk(".\\lotti\\"):
            for file in files:
                if file[-13:] == "ricevuta.json":
                    RICEVUTE.append(os.path.join(cartella, file))
        ULTIME_RICEVUTE = RICEVUTE[-10:]
        ULTIME_RICEVUTE.append("Inserisci manualmente.")
        RICEVUTA_TROVATA = False
        while RICEVUTA_TROVATA is False:
            print("\nRicevute degli ultimi lotti caricati:")
            nome_file_ricevuta = pyip.inputMenu(ULTIME_RICEVUTE, numbered = True, blank = True)
            if nome_file_ricevuta == "Inserisci manualmente.":
                nome_file_ricevuta = input("Inserisci il nome del file della ricevuta: ")
            try:
                with open(nome_file_ricevuta, "rb") as file:
                    DATI_LOTTO = json.load(file)
                    NOME_FILE_DATI = DATI_LOTTO.get("nomeFileDati")
                    PATH = DATI_LOTTO.get("cartellaDiLavoro")
                    DATA_LOTTO = DATI_LOTTO.get("data_lotto")
                    LOTTO_JSON = DATI_LOTTO.get("lotto_json")
                    LOTTO_LOG = DATI_LOTTO.get("lotto_log")
                    RICEVUTA_TROVATA = True
            except:
                print(f"\nFile {nome_file_ricevuta} non trovato.")
        print("\nFile della ricevuta trovato.")
        with open (LOTTO_JSON, "rb") as file:
                    LOTTO = json.load(file)
# Recupero l'invio (i messaggi già processati con successo non partono)
        statistiche, CF_ERRATI = invia_lotto(LOTTO, LOTTO_JSON)
        stampa("\nElaborazione degli invii terminata.")
        stampa(f"Consulta il file {LOTTO_JSON} per dettagli.")
        stampa(statistiche)
        if len(CF_ERRATI) > 0:
            stampa("----> ATTENZIONE! Ci sono dei codici fiscali apparentemente errati:")
            stampa("----> Verificali: " + str(CF_ERRATI))
        stampa("\nPuoi usare la funzione R di parlaConIO per ritentare invii in errore.")

#############################
### CONFIGURA PARLACONIO  ###
#############################
    elif scelta in ["C", "c"]:
        print("\n" + scelta + " - configurazione di parlaConIO")
        print("Per adesso, la configurazione è riservato all'amministatore di sistema.")
        print("Contattalo, anche se hai non ricordi la password.")
    
#############################
##### USCITA DAL PROGRAMMA ##
#############################
    else:
        print("Ciao " + CALLING_USER + ", è stato un piacere fare affari con te ;)")
        termina()
# Chiedo se si ha intenzione di continuare
    risposta = input("\nVuoi fare altre operazioni [S = sì / N = no]? ")
    while risposta not in ["S", "sì", "s", "Sì", "N", "no", "NO", "n"]:
        risposta = input("Non ho capito. Vuoi fare altre operazioni "\
                         "[S = sì / N = no]? ")
    if risposta in ["N", "no", "NO", "n"]:
        CONTINUARE = False
# Quando è tutto finito, termina
termina()
