# Inkbird Cook Control

Station e due IHT accesi insieme? Ognuno ha le proprie soglie e i propri avvisi.
Cambiare termometro cambia solo la vista: le altre cotture continuano.

**[Scarica Cook Control 1.2.0](https://github.com/zampix1/ha-inkbird-int14/releases/download/v0.2.11-beta.5/inkbird-cook-control-1.2.0.zip)**.
Il pacchetto in anteprima e' allegato alla prerelease, ma funziona anche con i
driver stabili. Il vecchio ZIP 1.1.0 segue ancora una cottura alla volta.
[English guide](README.md).

## Installazione

Devono gia' funzionare Inkbird INT per la station INT-14-BW, oppure
l'[integrazione IHT-2PB](https://github.com/zampix1/ha-inkbird-iht2pb-local).
Cook Control usa le loro entita', senza cambiare come comunicano con i dispositivi.

1. Fai un backup HA. Per passare dalla 1.1.0, aspetta la fine delle cotture.
2. Copia dal pacchetto le cartelle `custom_components`, `packages` e `www` nella
   directory di configurazione HA, normalmente `/config`. Unisci le cartelle:
   non sostituire l'intera cartella delle integrazioni. Non caricare due package BBQ.
3. Se non usi gia' i package, aggiungi questa voce sotto `homeassistant:` in
   `configuration.yaml`, senza duplicare la sezione:

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

4. Controlla la configurazione e riavvia. Il package carica il piccolo backend
   facoltativo `inkbird_cook_control`; i driver INT e IHT restano separati e intatti.
5. Aggiorna la risorsa JavaScript esistente in
   `/local/inkbird-int/inkbird-int-cook-control.js?v=1.2.0`, poi ricarica il browser.
6. Nella configurazione grezza della plancia esistente usa [dashboard.yaml](dashboard.yaml):

   ```yaml
   strategy:
     type: custom:inkbird-cook-control
   views: []
   ```

   Come nome scegli **Cook Control**. Il nuovo identificativo evita di riusare
   la vecchia interfaccia rimasta in memoria. Ricarica completamente il browser
   oppure chiudi e riapri l'app Companion.

Le nuove schede non richiedono button-card, card-mod o mini-graph-card.
Puoi lasciarli installati se servono ad altre plance. Per controlli e archivio
serve attualmente un account **amministratore HA**.

### Compare Ancora "Cambiare Termometro?"

L'avviso che parla di azzerare le soglie appartiene alla 1.1.0. Controlla che
ci sia una sola risorsa Cook Control, aggiornata a `?v=1.2.0`, e che la strategia
sia `custom:inkbird-cook-control`. Poi chiudi le vecchie schede HA e riapri l'app.
Non serve eliminare l'integrazione, rifare il pairing o azzerare la cottura.
Nella 1.2.0 il cambio vista non modifica soglie e avvisi.

## Nomi, Soglie E Cotture

Il selettore in alto mostra tutti i termometri riconosciuti. Con la matita puoi
chiamarli "Station BBQ", "Termometro cucina" o come ti torna comodo.
Nel campo della sonda scrivi la pietanza: "Musetto", "Pollo", "Brisket".

Alexa usera' quel nome: **"Musetto ha raggiunto 85 gradi"**. Modello e numero
fisico della sonda restano visibili per orientarti, senza finire per forza
nell'annuncio. Se lasci il nome generico, l'annuncio distingue sonda e termometro.

Imposta la soglia HA e attiva l'avviso. Parte anche la registrazione della cottura.
Puoi avviare prima lo storico, dandogli un nome, senza attivare nessun allarme.
Le soglie sono in Celsius; eventuali letture HA in Fahrenheit vengono convertite.

La station ha quattro sonde con cuore e ambiente. Ogni IHT ha punta integrata,
esterna 1 ed esterna 2: niente ambiente o quarta sonda inventati.

Per l'avviso servono almeno 30 secondi sopra soglia con dati recenti. Ogni
canale avvisa una volta per impostazione: cambiare nome, soglia o attivazione
prepara un nuovo avviso e annulla soltanto i suoi promemoria precedenti.
Cambiare termometro, invece, non modifica niente. Vale anche con due browser aperti.

**Termina cottura** archivia quella sessione e spegne soltanto i suoi avvisi.
Soglie e nomi rimangono. Le soglie HA non cambiano gli allarmi fisici del termometro.

## Echo E TV

In Impostazioni scegli **Alexa (native)** e l'Echo. Serve Alexa Media Player,
non ChatGPT o una chiave OpenAI. Per piu' Echo, inserisci un nome per il gruppo
annunci e le loro entita' `media_player`, separate da virgole. Aggiorna la lista
e seleziona quel gruppo. E' una lista di destinatari per gli annunci, non un gruppo
musicale Amazon: puoi includere la zona giorno e lasciare fuori le camere.

La TV e' indipendente: **popup di testo, senza audio**. Non fa parte del gruppo
Echo. Configura la sua entita' e il servizio notify senza il prefisso `notify.`.
Non accendiamo la TV, non cambiamo ingresso e non tocchiamo i volumi.

Il pulsante di prova serve proprio a controllare la consegna: una chiamata HA
senza errori non dimostra che l'Echo abbia parlato o che il popup sia apparso.

## Storico

Apri Storico per rivedere cotture attive e concluse, grafici, modifiche alle soglie
ed esiti degli avvisi. Puoi scaricare letture in CSV o l'intera sessione in JSON.
Si registra un campione ogni 30 secondi durante la cottura. Una sonda senza dati
recenti lascia un vuoto nel grafico, non una falsa lettura a zero.

L'archivio resta nella `.storage` privata di HA e non dipende dalla pulizia del
Recorder. Includilo nei backup. Gli export contengono nomi, orari, riferimenti
interni ai dispositivi e temperature: controllali prima di pubblicarli.
Le vecchie cotture non vengono inventate o ricostruite: l'archivio parte da qui.

Al primo avvio migriamo le impostazioni del termometro prima selezionato; gli
altri partono con soglie a zero e avvisi spenti. Echo/TV e vecchi helper vengono
conservati. Le vecchie automazioni condivise vengono disabilitate: non riattivarle
insieme al backend.

Soglie, avvisi gia' inviati e scadenze dei promemoria sopravvivono al riavvio.
L'attesa dei 30 secondi ricomincia; HA spento non puo' inviare avvisi.
Dati locali piu' vecchi di 120 secondi non fanno scattare nuove soglie.
La batteria raw dell'IHT non viene spacciata per percentuale. Batteria bassa e
stall rimangono avvisi opzionali; lo stall richiede uno storico recente e stabile.

## Tornare Indietro

Ripristina package, risorsa e frontend precedenti, rimuovi la voce
`inkbird_cook_control:` dal package, controlla la configurazione e riavvia.
Conserva l'archivio nel backup. Le soglie impostate nella 1.2.0 non vengono
ricopiate automaticamente nei vecchi helper della versione a cottura singola.

Per le origini della presentazione e le licenze vedi
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Comunicazione con i termometri
e protocollo restano lavoro delle integrazioni INT/IHT, non del tema della dashboard.
