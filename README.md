# parlaConIO2
Evoluzione del precedente parlaConIO.  

parlaConIO2 è allestito con le seguenti funzioni:
- 1 - invio lotto di avvisi di pagamento;  
- 2 - invio lotto di messaggi per scadenza della carta d'identità;  
- 3 - invio lotto di messaggi per scadenza PEC;  
- 4 - invio lotto di solleciti di pagamento;  
- 5 - verifica la diffusione di IO;  
- 6 - verifica la diffusione di IO per nucleo familiare [in preparazione];  
- R - recupera un precedente invio;  
- C - configurazione di parlaConIO;  
- U - esci da parlaConIO.  

Ogni funzione si aspetta in input un file CSV con alcuni dati utili all'invio del messaggio.  
Per ogni funzione è previsto un passaggio iniziale per fare il match fra parametri attesi dal messaggio e colonne/etichette presenti nel CSV.  

L'interazione - di tipo testuale - avviene da riga di comando.  

La funzione "R" consente di proseguire la spedizione di un lotto di messaggi precedentemente interrotta (per mancanza di rete o sovraccarico del server IO).

# Installazione e configurazione iniziale
Clonare il repository in una cartella (es.: "parlaConIO2").  

Modificare la sezione "COSTANTI LEGATE ALL'ENTE" (riga 26+) di parlaConIO2.py per adattarlo alla denominazione dell'ente e agli URL usati nei messaggi IO.  

Installare i moduli aggiunti Python necessari, se non presente (*pip -r requirements.txt*).

Nella sottocartella "cfg master":
- rinominare i tre file *.chiaro.RIMUOVIMI.cfg in *.chiaro.cfg;
- editare i tre file *.chiaro.cfg secondo il modello proposto, come segue:
 1. **IO.chiaro.cfg**: completare per ogni servizio IO conigurato nel back office di IO con codice/id (a scelta) per ogni servizio IO, APIKEY primaria e secondaria, id del servizio IO e il nome comprensibile;
 2. **pagoPA.chiaro.cfg**: completare per ogni servizio di incasso configurato presso il proprio partner tecnologico con il codice/id identificativo del servizio di incasso, il nome esteso e il codice/id del servizio IO tramite il quale inviare avvisi di pagamento;
 3. **permessi.chiaro.cfg**: completare con le funzioni parlaConIO da abilitare e i servizi IO da utilizzare.

Eseguire *prepara_cfg.py* e fornire una password master.  
Lo script produce tre file cifrati: *IO.master.cfg*, *pagoPA.master.cfg*, *permessi.master.cfg*.  
Copiare i file nella cartella "parlaConIO2".  
Eseguire lo script *parlaConIO2.py* e seguire le indicazioni: al primo avvio viene chiesta una password utente per l'esecuzione e, successivamente, la password master impostata al passo precedente.  
Al primo avvio i tre file .master.cfg sono ricifrati con la password utente e rinominati in *IO.cfg*, *pagoPA.cfg*, *permessi.cfg*.  
Eliminare (opzionale) i file .master.cfg.  
Se si perde la password occorre cancellare i tre file .cfg e ripetere il primo avvio.  

Se si vuole spostare lo script su un PC non dotato di Python si possono trasformare gli script *parlaConIO2.py* e *prepara_cfg.pyé in file eseguibili con pyInstaller:
- *pip install pyinstaller*
- *pyinstaller parlaConIO2.py --onefile*
- nella sottocartella "cfg master": *pyinstaller prepara_cfg.py --onefile*

Per configurare parlaConIO2 in un PC senza Python: creare una cartella "parlaConIO2" e copiarci i file *parlaConIO2.exe* e la sottocartella "cfg master" con l'eseguibile *prepara_cfg.exe* e i tre file di configurazione *.chiaro.cfg*.  
Seguire le istruzioni di sopra per il primo avvio/configurazione.

# Personalizzazioni
Il testo dei messaggi si può personalizzare intervendo nelle funzioni "crea_body_*", eventualmente anche aggiungendo argomenti/variabili che sono poi gestiti dalle funzioni "mappa" e "definisci_corrispondenze".

# Limitazioni e avvertenze
parlaConIO2 nasce come esperienza didattica per approfondire l'uso e il funzionamento delle API di IO.  
Rispetto alla prima versione sono stati migliorati alcuni aspetti di sicurezza (per esempio la memorizzazione delle APIKEY in chiaro nella cartella di lavoro).  
L'uso dello script per interazioni reali con IO è a rischio e pericolo dell'utilizzatore.  

In ogni caso, lo script è pensato per l'uso da parte di un umano che interagisce da riga di comando. Il riadattamento dello script all'interno di un processo automatico richiede ulteriori accorgimenti (es.: gestione più accurata di errori ed eccezioni e controllo più meticoloso dei dati in input).  
