const fs = require('fs');
const path = require('path');

// Read the English source file
const enPath = path.join(__dirname, '../messages/en.json');
const en = JSON.parse(fs.readFileSync(enPath, 'utf8'));

// Translation dictionaries for common terms
const translations = {
  nl: {
    // Dashboard
    "Loading dashboard...": "Dashboard laden...",
    "Here's your sales preparation overview.": "Hier is je salesvoorbereiding overzicht.",
    "Good morning": "Goedemorgen",
    "Good afternoon": "Goedemiddag",
    "Good evening": "Goedenavond",
    "Good night": "Goedenacht",
    "Start by creating your sales profile for personalized AI outputs": "Begin met het aanmaken van je salesprofiel voor gepersonaliseerde AI-output",
    "Add your company profile so the AI knows your products and services": "Voeg je bedrijfsprofiel toe zodat de AI je producten en diensten kent",
    "Research your first prospect to start your sales preparation": "Onderzoek je eerste prospect om je salesvoorbereiding te starten",
    "Research for {company} is ready - now add a contact person": "Onderzoek voor {company} is klaar - voeg nu een contactpersoon toe",
    "After your meeting: upload the recording for transcription and follow-up actions": "Na je meeting: upload de opname voor transcriptie en follow-up acties",
    "Had a meeting with {company}? Upload the recording for follow-up": "Meeting gehad met {company}? Upload de opname voor follow-up",
    "Great job! Your sales preparation is on track 🎉": "Goed bezig! Je salesvoorbereiding is op schema 🎉",
    "Create Profile": "Profiel aanmaken",
    "Add Company": "Bedrijf toevoegen",
    "Start Research": "Start onderzoek",
    "Add Contact": "Contact toevoegen",
    "Upload Meeting": "Meeting uploaden",
    "Analyze": "Analyseren",
    "New Prospect": "Nieuwe prospect",
    "Prepare": "Voorbereiden",
    "Complete": "Voltooid",
    "Research in progress...": "Onderzoek bezig...",
    "My Prospects": "Mijn prospects",
    "No prospects yet": "Nog geen prospects",
    "Start with your first prospect research": "Begin met je eerste prospectonderzoek",
    "View all {count} prospects": "Bekijk alle {count} prospects",
    "This Week": "Deze week",
    "Research": "Onderzoek",
    "Preparations": "Voorbereidingen",
    "Follow-ups": "Follow-ups",
    "Quick Actions": "Snelle acties",
    "New Research": "Nieuw onderzoek",
    "New Preparation": "Nieuwe voorbereiding",
    "Analyze Meeting": "Meeting analyseren",
    "Sales Profile": "Salesprofiel",
    "Company Profile": "Bedrijfsprofiel",
    "Incomplete": "Onvolledig",
    "{count} documents": "{count} documenten",
    "Luna • AI Sales Coach": "Luna • AI Sales Coach",
    "Flow Usage": "Flow gebruik",
    "Unlimited": "Onbeperkt",
    "{remaining} flows remaining": "{remaining} flows over",
    "Upgrade Plan": "Plan upgraden",
    "Recent Activity": "Recente activiteit",
    "Research completed: {company}": "Onderzoek voltooid: {company}",
    "Prep generated: {company}": "Voorbereiding gegenereerd: {company}",
    "Meeting analyzed: {company}": "Meeting geanalyseerd: {company}",
    "Contact added: {company}": "Contact toegevoegd: {company}",
    "Research started!": "Onderzoek gestart!",
    "Your prospect will be created automatically": "Je prospect wordt automatisch aangemaakt",
    "Preparation started!": "Voorbereiding gestart!",
    "Your meeting brief is being generated": "Je meetingbrief wordt gegenereerd",
    "Follow-up started!": "Follow-up gestart!",
    "Your recording is being processed": "Je opname wordt verwerkt",
    "Research a new prospect company": "Onderzoek een nieuw prospectbedrijf",
    "Create a personalized meeting preparation": "Maak een gepersonaliseerde meetingvoorbereiding",
    "Upload and analyze your meeting recording": "Upload en analyseer je meetingopname",
    
    // Common
    "Loading...": "Laden...",
    "Save": "Opslaan",
    "Cancel": "Annuleren",
    "Delete": "Verwijderen",
    "Edit": "Bewerken",
    "View": "Bekijken",
    "Back": "Terug",
    "Next": "Volgende",
    "Search": "Zoeken",
    "Select:": "Selecteer:",
    "Close": "Sluiten",
    "Copy": "Kopiëren",
    "Copied!": "Gekopieerd!",
    "Refresh": "Vernieuwen",
    "Add": "Toevoegen",
    "Remove": "Verwijderen",
    "Yes": "Ja",
    "No": "Nee",
    "or": "of",
    "and": "en",
    "Upload Documents": "Documenten uploaden",
    "Download": "Downloaden",
    "Extra options": "Extra opties",
    "Confirm": "Bevestigen",
    "Processing...": "Verwerken...",
    "optional": "optioneel",
    "required": "verplicht",
    "Markdown file downloaded": "Markdown-bestand gedownload",
    "PDF file downloaded": "PDF-bestand gedownload",
    "Word file downloaded": "Word-bestand gedownload",
    "Failed to export PDF": "PDF exporteren mislukt",
    "Failed to export Word document": "Word-document exporteren mislukt",
    
    // Navigation
    "Dashboard": "Dashboard",
    "Prospects": "Prospects",
    "Preparation": "Voorbereiding",
    "Meetings": "Meetings",
    "Meeting Analysis": "Meetinganalyse",
    "Recordings": "Opnames",
    "Profile": "Profiel",
    "Knowledge Base": "Kennisbank",
    "Settings": "Instellingen",
    "Log out": "Uitloggen",
    "Main": "Hoofd",
    "Profiles": "Profielen",
    "Notifications": "Meldingen",
    "{count, plural, =0 {No notifications} one {# notification} other {# notifications}}": "{count, plural, =0 {Geen meldingen} one {# melding} other {# meldingen}}",
    "Open menu": "Menu openen",
    
    // Auth
    "Log in": "Inloggen",
    "Sign up": "Registreren",
    "Email address": "E-mailadres",
    "Password": "Wachtwoord",
    "Forgot password?": "Wachtwoord vergeten?",
    "Don't have an account?": "Nog geen account?",
    "Already have an account?": "Al een account?",
    "Continue with Google": "Doorgaan met Google",
    "Continue with Microsoft": "Doorgaan met Microsoft",
    
    // Status
    "Completed": "Voltooid",
    "In progress": "Bezig",
    "Failed": "Mislukt",
    "Pending": "In behandeling",
    "New": "Nieuw",
    
    // Time
    "Just now": "Zojuist",
    "{count} min ago": "{count} min geleden",
    "{count} hours ago": "{count} uur geleden",
    "Yesterday": "Gisteren",
    "{count} days ago": "{count} dagen geleden",
    
    // Errors
    "Something went wrong": "Er is iets misgegaan",
    "Network error, please try again": "Netwerkfout, probeer het opnieuw",
    "Unauthorized": "Niet geautoriseerd",
    "Not found": "Niet gevonden",
    "Please check your input": "Controleer je invoer",
    "Request timed out, please try again": "Verzoek verlopen, probeer het opnieuw",
    "Server error, please try again later": "Serverfout, probeer het later opnieuw",
    "You don't have permission to perform this action": "Je hebt geen toestemming voor deze actie",
    "File is too large (max {maxSize})": "Bestand is te groot (max {maxSize})",
    "Invalid file type": "Ongeldig bestandstype",
    "Upload failed, please try again": "Upload mislukt, probeer het opnieuw",
    "Delete failed, please try again": "Verwijderen mislukt, probeer het opnieuw",
    "Could not save changes": "Wijzigingen konden niet worden opgeslagen",
    "Could not load data": "Data kon niet worden geladen",
    "Your session has expired, please log in again": "Je sessie is verlopen, log opnieuw in",
    "Too many requests, please wait a moment": "Te veel verzoeken, wacht even",
    "Usage limit reached. Upgrade your plan to continue.": "Gebruikslimiet bereikt. Upgrade je plan om door te gaan.",
    "Try again": "Probeer opnieuw",
    "Go back": "Ga terug",
    "Contact support if this problem persists": "Neem contact op met support als dit probleem aanhoudt",
    "An unexpected error occurred. Our team has been notified and is working on a fix.": "Er is een onverwachte fout opgetreden. Ons team is op de hoogte gesteld en werkt aan een oplossing.",
    "Go to Dashboard": "Ga naar Dashboard",
    "Error details (development only)": "Foutdetails (alleen development)"
  }
};

// Deep translation function
function translateObject(obj, lang) {
  const dict = translations[lang] || {};
  
  if (typeof obj === 'string') {
    return dict[obj] || obj;
  }
  
  if (Array.isArray(obj)) {
    return obj.map(item => translateObject(item, lang));
  }
  
  if (typeof obj === 'object' && obj !== null) {
    const result = {};
    for (const key in obj) {
      result[key] = translateObject(obj[key], lang);
    }
    return result;
  }
  
  return obj;
}

// Generate translations
const languages = ['nl', 'de', 'fr', 'es', 'hi', 'ar'];

console.log('Translation script created. Run with full dictionaries to generate files.');
console.log('Due to size constraints, please use an external translation service or API.');

