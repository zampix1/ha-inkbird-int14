# Inkbird Cook Control

Scegli il termometro, imposta la soglia e lascia che sia l'Echo ad avvisarti.
Cook Control riunisce letture, grafici e avvisi di INT-14-BW e IHT-2PB in una
dashboard facoltativa. L'integrazione funziona anche senza.

**Cook Control 1.1.0 aggiunge IHT-2PB e la scelta del termometro.**
La station INT-14-BW e ciascun IHT-2PB gia' configurato in HA compaiono separatamente.
Si segue una cottura alla volta: non sono sessioni indipendenti contemporanee.

Lo ZIP funziona anche con l'integrazione stabile. Lo trovi tra gli allegati di
v0.2.11-beta.4, ma non serve installare la beta Bluetooth per usare la dashboard.

## Installazione

Prima devono funzionare Inkbird INT e le otto temperature della station, oppure
l'[integrazione separata IHT-2PB](https://github.com/zampix1/ha-inkbird-iht2pb-local)
e i suoi tre canali di temperatura.
Da HACS installa anche **button-card**, **card-mod** e **mini-graph-card**.

**[Scarica Cook Control 1.1.0](https://github.com/zampix1/ha-inkbird-int14/releases/download/v0.2.11-beta.4/inkbird-cook-control-1.1.0.zip)**

Estrai prima lo ZIP. La directory di configurazione HA e' quella che contiene
`configuration.yaml`, normalmente `/config`. Unisci le due cartelle a quelle
esistenti: non copiare lo ZIP intero o una cartella contenitore aggiuntiva.
Alla fine la struttura deve essere questa:

```text
config/
  configuration.yaml
  packages/inkbird_bbq.yaml
  www/inkbird-int/cook-base-v1.4.3.js
  www/inkbird-int/inkbird-int-cook-model.mjs
  www/inkbird-int/inkbird-int-cook-control.js
```

La cartella `cook-control` nello ZIP contiene guide, licenze e YAML della
plancia: non serve copiarla in HA.

1. Fai un backup HA. Copia `packages` e `www` del pacchetto nella directory di
   configurazione. Se usi gia' il pacchetto BBQ di Remco, sostituiscilo:
   **non caricare due copie**. Gli helper mantengono gli stessi ID.
2. Se non usi gia' i package, aggiungi questa voce in `configuration.yaml`.
   Se esiste gia' `homeassistant:`, aggiungi solo la riga `packages:` sotto
   quella sezione, con due spazi davanti, senza duplicarla:

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

   Controlla la configurazione e riavvia HA a cottura finita.
3. In **Impostazioni > Plance > Risorse**, aggiungi il modulo JavaScript
   `/local/inkbird-int/inkbird-int-cook-control.js?v=1.1.0`.
   Se manca Risorse, abilita Modalita' avanzata nel profilo. Per aggiornare,
   modifica la risorsa esistente invece di aggiungerne un'altra. Ricarica il browser.
4. Aggiungi **Inkbird Cook Control** dalle dashboard della community. In
   alternativa crea una plancia vuota e incolla [dashboard.yaml](dashboard.yaml)
   nel suo editor di configurazione grezza:

   ```yaml
   strategy:
     type: custom:inkbird-int-cook-control
   views: []
   ```

5. Scegli il dispositivo nel riquadro **Termometro** e scegli **Italiano**.
   I termometri dello stesso modello restano distinguibili. Il prefisso si configura
   una volta sola; non tocchiamo i parametri del termometro.

Con un rilevamento ambiguo, vedi il [prefisso esplicito](README.md#install).
Il pacchetto segue un termometro alla volta. HACS installa l'integrazione, non questa
dashboard facoltativa.

## Se Usi Gia' Cook Control

A cottura finita, fai un backup e sostituisci `packages/inkbird_bbq.yaml` e i tre
file in `www/inkbird-int`. Mantieni gli stessi helper e la stessa plancia.
Nella risorsa gia' presente cambia solo il finale dell'URL in `?v=1.1.0`.
Controlla la configurazione, riavvia HA e ricarica il browser. Non aggiungere
una seconda copia del package o della risorsa.

Termometro selezionato, soglie, nomi e impostazioni Echo/TV vengono mantenuti.
Non serve riselezionare lo stesso dispositivo. **Le soglie vengono azzerate
solo quando confermi il passaggio a un altro termometro.**

## Cambiare Termometro

Il cambio disattiva tutti gli avvisi, cancella i promemoria in attesa e azzera
le vecchie soglie HA. Imposta quelle della nuova cottura e attiva i canali usati:
una sonda gia' calda non deve far partire l'allarme della cottura precedente.
Echo e TV restano quelli scelti nelle impostazioni.

Con IHT-2PB le tre schede sono **punta integrata**, **esterna 1**, **esterna 2**.
Niente temperatura ambiente e niente quarta sonda inventata. Una sonda scollegata
resta senza lettura. La batteria e' un livello raw, non una percentuale. Come per
la station, le soglie HA non cambiano gli allarmi fisici del dispositivo.

## Cottura E Avvisi

Dai un nome alla sonda, tocca la card per impostare la **soglia HA** e abilita
gli avvisi solo sulle sonde usate. Per una nuova cottura disattivali e riattivali.
La soglia HA serve agli annunci; l'**allarme station** e' quello riportato dal
termometro. I preset non modificano l'allarme del dispositivo.

L'avviso parte dopo 30 secondi sopra soglia. La riconnessione non lo ripete.
**Ignora/Dismiss** ferma rinvio e promemoria. Cambiare nome, soglia o termometro
cancella i timer precedenti. Il promemoria decorre dalla soglia, non da quando
togli il cibo dal fuoco. Le temperature dei preset non garantiscono sicurezza
o cottura riuscita: continua a controllare il cibo.

Per Echo seleziona il dispositivo, **Alexa (native)** e attiva gli annunci.
Serve **Alexa Media Player**, non OpenAI. Per la TV configura entita' e servizio
notify, poi prova il pulsante. La LG mostra un popup breve **senza audio**:
non cambiamo volume, ingresso o stato di accensione.

Gli avvisi HA persistenti vengono creati per primi. Verifica di persona gli
altri canali: una chiamata accettata non certifica che tu l'abbia sentita.

## Limiti

- Oltre 120 secondi senza pacchetti locali, le letture non alimentano nuovi
  allarmi; il controllo temporale HA puo' aggiungere fino a un minuto.
- I timer non sopravvivono a riavvio HA o ricarica delle automazioni.
- Le batterie sono quelle dichiarate dalla station. Un valore sospetto viene
  segnalato, non sostituito con una percentuale inventata.
- Stallo e batteria bassa sono avvisi facoltativi, non sistemi di sicurezza.
- Prove reali e simulate sono distinte in [VALIDATION.md](VALIDATION.md).

La base grafica deriva dal lavoro MIT di Remco, con i crediti di design
conservati. Comunicazione e protocollo arrivano dalle integrazioni separate
`zampix1/ha-inkbird-int14` e `zampix1/ha-inkbird-iht2pb-local`.
Vedi [fonti e licenze](THIRD_PARTY_NOTICES.md).

Per tornare indietro ripristina package e dashboard dal backup, controlla la
configurazione e riavvia HA. Non serve rifare il pairing.
