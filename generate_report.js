const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, LevelFormat,
  ExternalHyperlink, TableOfContents,
} = require('docx');
const fs = require('fs');

// ─── Couleurs ────────────────────────────────────────────────────────────────
const TEAL      = "00B4A0";
const DARK      = "1A1A2E";
const ACCENT    = "3D7FFF";
const GRAY      = "555555";
const LIGHTGRAY = "F2F4F8";
const WHITE     = "FFFFFF";
const BLACK     = "000000";

// ─── Borders helper ──────────────────────────────────────────────────────────
const border = (color = "CCCCCC") => ({ style: BorderStyle.SINGLE, size: 1, color });
const borders = (color = "CCCCCC") => ({ top: border(color), bottom: border(color), left: border(color), right: border(color) });
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

// ─── Helpers ─────────────────────────────────────────────────────────────────
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, bold: true, size: 36, color: DARK, font: "Arial" })],
    spacing: { before: 480, after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: TEAL, space: 4 } },
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, bold: true, size: 28, color: TEAL, font: "Arial" })],
    spacing: { before: 320, after: 160 },
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text, bold: true, size: 24, color: DARK, font: "Arial" })],
    spacing: { before: 200, after: 120 },
  });
}

function p(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: 22, font: "Arial", color: GRAY, ...opts })],
    spacing: { before: 80, after: 120 },
    alignment: AlignmentType.JUSTIFIED,
  });
}

function bold(text) {
  return new TextRun({ text, bold: true, size: 22, font: "Arial", color: DARK });
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: [new TextRun({ text, size: 22, font: "Arial", color: GRAY })],
    spacing: { before: 60, after: 60 },
  });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function spacer(lines = 1) {
  return new Paragraph({ children: [new TextRun("")], spacing: { before: 0, after: 200 * lines } });
}

function centered(text, opts = {}) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text, font: "Arial", ...opts })],
    spacing: { before: 80, after: 80 },
  });
}

// ─── Tableau tech stack ───────────────────────────────────────────────────────
function techTable(rows) {
  return new Table({
    width: { size: 9026, type: WidthType.DXA },
    columnWidths: [2500, 3263, 3263],
    rows: [
      new TableRow({
        children: [
          { text: "Catégorie", w: 2500 },
          { text: "Technologie", w: 3263 },
          { text: "Rôle", w: 3263 },
        ].map(c => new TableCell({
          borders: borders(TEAL),
          width: { size: c.w, type: WidthType.DXA },
          shading: { fill: TEAL, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: c.text, bold: true, color: WHITE, size: 20, font: "Arial" })] })],
        })),
      }),
      ...rows.map((r, i) => new TableRow({
        children: r.map((cell, ci) => new TableCell({
          borders: borders("CCCCCC"),
          width: { size: [2500, 3263, 3263][ci], type: WidthType.DXA },
          shading: { fill: i % 2 === 0 ? LIGHTGRAY : WHITE, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: cell, size: 20, font: "Arial", color: GRAY })] })],
        })),
      })),
    ],
  });
}

// ─── Tableau simple 2 colonnes ────────────────────────────────────────────────
function twoColTable(rows, col1Width = 3000) {
  const col2Width = 9026 - col1Width;
  return new Table({
    width: { size: 9026, type: WidthType.DXA },
    columnWidths: [col1Width, col2Width],
    rows: rows.map((r, i) => new TableRow({
      children: [
        new TableCell({
          borders: borders("CCCCCC"),
          width: { size: col1Width, type: WidthType.DXA },
          shading: { fill: i % 2 === 0 ? "E8F5F3" : WHITE, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: r[0], bold: true, size: 20, font: "Arial", color: DARK })] })],
        }),
        new TableCell({
          borders: borders("CCCCCC"),
          width: { size: col2Width, type: WidthType.DXA },
          shading: { fill: i % 2 === 0 ? LIGHTGRAY : WHITE, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: r[1], size: 20, font: "Arial", color: GRAY })] })],
        }),
      ],
    })),
  });
}

// ─── DOCUMENT ─────────────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "•",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } },
      }],
    }],
  },
  styles: {
    default: {
      document: { run: { font: "Arial", size: 22, color: GRAY } },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: DARK },
        paragraph: { spacing: { before: 480, after: 200 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: TEAL },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 1 },
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: DARK },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 },
      },
    ],
  },

  sections: [
    // ═══════════════════════════════════════════════════════════════════════════
    // PAGE DE GARDE
    // ═══════════════════════════════════════════════════════════════════════════
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      children: [
        spacer(1),
        // Bandeau établissement
        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [9026],
          rows: [new TableRow({ children: [new TableCell({
            borders: borders(TEAL),
            width: { size: 9026, type: WidthType.DXA },
            shading: { fill: TEAL, type: ShadingType.CLEAR },
            margins: { top: 200, bottom: 200, left: 300, right: 300 },
            children: [
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "ÉCOLE SUPÉRIEURE DE TECHNOLOGIE DE TÉTOUAN", bold: true, size: 24, color: WHITE, font: "Arial" })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Université Abdelmalek Essaâdi", size: 20, color: WHITE, font: "Arial" })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Filière : Intelligence Artificielle — 2ème Année", size: 20, color: WHITE, font: "Arial", italics: true })] }),
            ],
          })]})]
        }),

        spacer(2),

        centered("RAPPORT DE PROJET DE FIN D'ÉTUDES", { bold: true, size: 28, color: GRAY }),
        spacer(1),

        // Titre du projet
        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [9026],
          rows: [new TableRow({ children: [new TableCell({
            borders: borders(ACCENT),
            width: { size: 9026, type: WidthType.DXA },
            shading: { fill: DARK, type: ShadingType.CLEAR },
            margins: { top: 300, bottom: 300, left: 400, right: 400 },
            children: [
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Plateforme IA Intelligente", bold: true, size: 40, color: WHITE, font: "Arial" })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "AutoML Agentique & Migration de Code LLM", bold: true, size: 28, color: "00D4AA", font: "Arial" })] }),
              spacer(0),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "v2.0 PFE", size: 20, color: "888888", font: "Arial", italics: true })] }),
            ],
          })]})]
        }),

        spacer(2),

        // Étudiants
        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [4400, 4626],
          rows: [
            new TableRow({ children: [
              new TableCell({
                borders: borders(TEAL),
                width: { size: 4400, type: WidthType.DXA },
                shading: { fill: "E8F5F3", type: ShadingType.CLEAR },
                margins: { top: 200, bottom: 200, left: 200, right: 200 },
                children: [
                  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Réalisé par", bold: true, size: 22, color: TEAL, font: "Arial" })] }),
                  spacer(0),
                  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Ahmed Abdelmoumen", bold: true, size: 24, color: DARK, font: "Arial" })] }),
                  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Bassma Haja", bold: true, size: 24, color: DARK, font: "Arial" })] }),
                  spacer(0),
                  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Étudiants 2ème année — Filière IA", size: 20, color: GRAY, font: "Arial", italics: true })] }),
                ],
              }),
              new TableCell({
                borders: borders(ACCENT),
                width: { size: 4626, type: WidthType.DXA },
                shading: { fill: "EEF3FF", type: ShadingType.CLEAR },
                margins: { top: 200, bottom: 200, left: 200, right: 200 },
                children: [
                  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Informations", bold: true, size: 22, color: ACCENT, font: "Arial" })] }),
                  spacer(0),
                  new Paragraph({ children: [new TextRun({ text: "Établissement : ", bold: true, size: 20, font: "Arial", color: DARK }), new TextRun({ text: "EST Tétouan", size: 20, font: "Arial", color: GRAY })] }),
                  new Paragraph({ children: [new TextRun({ text: "Filière : ", bold: true, size: 20, font: "Arial", color: DARK }), new TextRun({ text: "Intelligence Artificielle", size: 20, font: "Arial", color: GRAY })] }),
                  new Paragraph({ children: [new TextRun({ text: "Niveau : ", bold: true, size: 20, font: "Arial", color: DARK }), new TextRun({ text: "2ème Année", size: 20, font: "Arial", color: GRAY })] }),
                  new Paragraph({ children: [new TextRun({ text: "Année : ", bold: true, size: 20, font: "Arial", color: DARK }), new TextRun({ text: "2025 – 2026", size: 20, font: "Arial", color: GRAY })] }),
                ],
              }),
            ]}),
          ],
        }),

        spacer(2),
        centered("Année Universitaire 2025 – 2026", { size: 22, color: GRAY }),
      ],
    },

    // ═══════════════════════════════════════════════════════════════════════════
    // CORPS DU RAPPORT
    // ═══════════════════════════════════════════════════════════════════════════
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1440, right: 1260, bottom: 1440, left: 1260 },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              children: [
                new TextRun({ text: "Plateforme IA — AutoML & Migration | EST Tétouan", size: 18, color: TEAL, font: "Arial" }),
                new TextRun({ text: "\t", size: 18 }),
                new TextRun({ text: "Ahmed Abdelmoumen & Bassma Haja", size: 18, color: GRAY, font: "Arial" }),
              ],
              tabStops: [{ type: "right", position: 9026 }],
              border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: TEAL, space: 2 } },
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              children: [
                new TextRun({ text: "Rapport PFE — Filière Intelligence Artificielle, EST Tétouan  |  ", size: 16, color: GRAY, font: "Arial" }),
                new TextRun({ children: [PageNumber.CURRENT], size: 16, color: TEAL, bold: true, font: "Arial" }),
              ],
              border: { top: { style: BorderStyle.SINGLE, size: 4, color: TEAL, space: 2 } },
            }),
          ],
        }),
      },
      children: [

        // ─── DÉDICACES ───────────────────────────────────────────────────────────
        h1("Dédicaces"),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "", size: 22 })],
          spacing: { before: 400, after: 400 },
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "À nos familles, pour leur soutien indéfectible tout au long de notre parcours académique.", size: 24, italics: true, color: DARK, font: "Arial" })],
          spacing: { before: 200, after: 200 },
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "À nos encadrants et enseignants de l'EST Tétouan,", size: 22, italics: true, color: GRAY, font: "Arial" })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "pour leurs précieux conseils et leur accompagnement bienveillant.", size: 22, italics: true, color: GRAY, font: "Arial" })],
          spacing: { before: 0, after: 200 },
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "À tous nos camarades de la filière Intelligence Artificielle,", size: 22, italics: true, color: GRAY, font: "Arial" })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "avec qui nous avons partagé cette belle aventure.", size: 22, italics: true, color: GRAY, font: "Arial" })],
        }),
        pageBreak(),

        // ─── REMERCIEMENTS ───────────────────────────────────────────────────────
        h1("Remerciements"),
        p("Nous tenons à exprimer notre profonde gratitude à toutes les personnes qui ont contribué, de près ou de loin, à la réalisation de ce projet de fin d'études."),
        p("Nos remerciements les plus sincères vont à notre encadrant pédagogique, pour sa disponibilité, sa rigueur et ses précieux conseils qui ont guidé notre travail tout au long de ce projet."),
        p("Nous remercions également l'ensemble du corps enseignant de l'École Supérieure de Technologie de Tétouan, et plus particulièrement les professeurs de la filière Intelligence Artificielle, pour la qualité de la formation qu'ils nous ont dispensée."),
        p("Nos remerciements s'adressent aussi à nos familles pour leur soutien moral constant, leur patience et leurs encouragements tout au long de notre cursus universitaire."),
        p("Enfin, nous remercions la communauté open-source pour les outils et bibliothèques qui ont rendu ce projet possible : FastAPI, React, scikit-learn, Optuna, OpenAI GPT-4o, et bien d'autres."),
        pageBreak(),

        // ─── RÉSUMÉ ──────────────────────────────────────────────────────────────
        h1("Résumé"),
        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [9026],
          rows: [new TableRow({ children: [new TableCell({
            borders: borders(TEAL),
            width: { size: 9026, type: WidthType.DXA },
            shading: { fill: "E8F5F3", type: ShadingType.CLEAR },
            margins: { top: 200, bottom: 200, left: 240, right: 240 },
            children: [
              new Paragraph({ children: [new TextRun({ text: "Résumé (Français)", bold: true, size: 22, color: TEAL, font: "Arial" })], spacing: { after: 120 } }),
              new Paragraph({
                alignment: AlignmentType.JUSTIFIED,
                children: [new TextRun({ text: "Ce projet de fin d'études présente la conception et le développement d'une plateforme intelligente intégrant deux modules principaux : un module AutoML agentique et un module de migration de code assisté par LLM. Le module AutoML permet aux utilisateurs non-experts en machine learning de créer automatiquement des pipelines d'apprentissage automatique optimisés via un agent LLM (GPT-4o) qui analyse les datasets, propose des stratégies de nettoyage et d'ingénierie de features, sélectionne les meilleurs algorithmes et optimise les hyperparamètres avec Optuna. Le module de migration de code prend en charge la migration de fichiers Java et Python vers des versions plus récentes, en utilisant une architecture multi-agents (Analyste, Migrateur, Vérificateur) pour garantir la qualité du code migré. La plateforme est développée avec FastAPI (backend) et React (frontend), et déployée via GitHub.", size: 20, font: "Arial", color: GRAY })],
                spacing: { after: 160 },
              }),
              new Paragraph({ children: [new TextRun({ text: "Mots-clés : ", bold: true, size: 20, color: DARK, font: "Arial" }), new TextRun({ text: "AutoML, LLM, GPT-4o, FastAPI, React, Migration de code, Multi-agents, Optuna, scikit-learn", size: 20, color: GRAY, font: "Arial" })] }),
            ],
          })]})]
        }),
        spacer(1),
        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [9026],
          rows: [new TableRow({ children: [new TableCell({
            borders: borders(ACCENT),
            width: { size: 9026, type: WidthType.DXA },
            shading: { fill: "EEF3FF", type: ShadingType.CLEAR },
            margins: { top: 200, bottom: 200, left: 240, right: 240 },
            children: [
              new Paragraph({ children: [new TextRun({ text: "Abstract (English)", bold: true, size: 22, color: ACCENT, font: "Arial" })], spacing: { after: 120 } }),
              new Paragraph({
                alignment: AlignmentType.JUSTIFIED,
                children: [new TextRun({ text: "This final year project presents the design and development of an intelligent platform integrating two main modules: an agentic AutoML module and an LLM-assisted code migration module. The AutoML module allows non-expert users to automatically create optimized machine learning pipelines via a GPT-4o agent that analyzes datasets, proposes cleaning and feature engineering strategies, selects the best algorithms, and optimizes hyperparameters with Optuna. The code migration module handles the migration of Java and Python files to more recent versions, using a multi-agent architecture (Analyzer, Migrator, Verifier) to ensure the quality of the migrated code. The platform is developed with FastAPI (backend) and React (frontend), and deployed via GitHub.", size: 20, font: "Arial", color: GRAY })],
                spacing: { after: 160 },
              }),
              new Paragraph({ children: [new TextRun({ text: "Keywords: ", bold: true, size: 20, color: DARK, font: "Arial" }), new TextRun({ text: "AutoML, LLM, GPT-4o, FastAPI, React, Code Migration, Multi-agents, Optuna, scikit-learn", size: 20, color: GRAY, font: "Arial" })] }),
            ],
          })]})]
        }),
        pageBreak(),

        // ─── TABLE DES MATIÈRES ───────────────────────────────────────────────────
        h1("Table des Matières"),
        new TableOfContents("Table des Matières", { hyperlink: true, headingStyleRange: "1-3" }),
        pageBreak(),

        // ═══════════════════════════════════════════════════════════════════════════
        // INTRODUCTION GÉNÉRALE
        // ═══════════════════════════════════════════════════════════════════════════
        h1("Introduction Générale"),
        p("L'intelligence artificielle connaît une révolution sans précédent, transformant profondément les pratiques dans de nombreux domaines. Parmi les avancées les plus remarquables, l'AutoML (Automated Machine Learning) et les modèles de langage de grande taille (LLM) représentent deux axes majeurs qui redéfinissent la façon dont les applications intelligentes sont conçues et maintenues."),
        p("Dans ce contexte, notre projet de fin d'études s'inscrit dans une démarche d'innovation visant à démocratiser l'accès à l'intelligence artificielle tout en facilitant la modernisation des bases de code existantes. Nous avons développé une plateforme web complète intégrant deux modules complémentaires :"),
        bullet("Un module AutoML agentique qui automatise la création de pipelines de machine learning en s'appuyant sur un agent LLM (GPT-4o) capable d'analyser des datasets, de proposer des stratégies de nettoyage, d'ingénierie de features et de sélectionner les meilleurs modèles."),
        bullet("Un module de migration de code qui assiste les développeurs dans la modernisation de leurs fichiers Java et Python, en utilisant une architecture multi-agents pour garantir la qualité et la cohérence du code migré."),
        spacer(0),
        p("Ce rapport est structuré en cinq chapitres : le premier présente le contexte et les besoins du projet, le second décrit l'architecture générale de la plateforme, les troisième et quatrième chapitres détaillent respectivement les modules AutoML et Migration, et le cinquième présente les tests et résultats obtenus."),
        pageBreak(),

        // ═══════════════════════════════════════════════════════════════════════════
        // CHAPITRE 1
        // ═══════════════════════════════════════════════════════════════════════════
        h1("Chapitre 1 : Contexte et Analyse des Besoins"),

        h2("1.1 Contexte du Projet"),
        p("Le projet s'inscrit dans le cadre de la formation en Intelligence Artificielle à l'École Supérieure de Technologie de Tétouan (EST Tétouan). L'objectif est de mettre en pratique les compétences acquises tout au long de la formation en développant une application web complète intégrant des concepts avancés d'IA."),
        p("La problématique centrale autour de laquelle s'articule ce projet peut être formulée comme suit : comment rendre l'intelligence artificielle accessible à des utilisateurs non-experts tout en offrant aux développeurs des outils pour moderniser leur code legacy ?"),

        h2("1.2 Problématique"),
        h3("1.2.1 Le défi de l'AutoML"),
        p("La création de pipelines de machine learning représente un processus complexe et chronophage qui nécessite des compétences approfondies en data science. Les étapes de nettoyage des données, d'ingénierie des features, de sélection des algorithmes et d'optimisation des hyperparamètres constituent autant d'obstacles pour les non-experts. L'AutoML vise à automatiser ces étapes, mais les solutions existantes manquent souvent d'explicabilité et de personnalisation."),
        h3("1.2.2 Le défi de la migration de code"),
        p("Les bases de code Java et Python vieillissantes constituent un enjeu majeur pour de nombreuses organisations. Les mauvaises pratiques de codage accumulées au fil des années (raw types, gestion d'erreurs incorrecte, APIs obsolètes) représentent des risques de sécurité et de performance. La migration manuelle est coûteuse et sujette aux erreurs humaines."),

        h2("1.3 Objectifs du Projet"),
        bullet("Développer une interface web intuitive et moderne pour les deux modules"),
        bullet("Implémenter un agent AutoML capable d'analyser automatiquement les datasets et de proposer des pipelines optimisés"),
        bullet("Créer un système de migration de code assisté par LLM avec évaluation de la qualité avant/après"),
        bullet("Intégrer une architecture multi-agents pour améliorer la qualité des résultats"),
        bullet("Mettre en place un système de scoring de la qualité du code"),
        bullet("Déployer la plateforme sur GitHub avec versioning"),

        h2("1.4 Analyse des Besoins"),
        h3("1.4.1 Besoins fonctionnels"),
        spacer(0),
        twoColTable([
          ["Upload de dataset", "Chargement de fichiers CSV avec prévisualisation et statistiques"],
          ["Analyse AutoML", "Analyse automatique des colonnes, détection des types, statistiques descriptives"],
          ["Pipeline agentique", "Génération automatique d'un pipeline ML par agent GPT-4o"],
          ["Entraînement", "Entraînement multi-modèles avec optimisation Optuna"],
          ["Prédiction", "Interface de prédiction sur nouveaux exemples"],
          ["Upload de code", "Chargement de fichiers .java et .py"],
          ["Migration LLM", "Migration vers Java 8/11/17/21 ou Python 3.8/3.10/3.12"],
          ["Scoring qualité", "Évaluation avant/après avec score 0-100 et grade A-F"],
          ["Multi-agents", "Pipeline Analyste + Migrateur + Vérificateur"],
          ["Téléchargement", "Export du code migré"],
        ]),
        spacer(1),
        h3("1.4.2 Besoins non fonctionnels"),
        bullet("Performance : temps de réponse < 30s pour les opérations LLM"),
        bullet("Scalabilité : architecture modulaire permettant l'ajout de nouveaux modules"),
        bullet("Sécurité : validation des fichiers uploadés, taille maximale 1 MB"),
        bullet("Maintenabilité : code structuré avec séparation des responsabilités"),
        bullet("Ergonomie : interface responsive et intuitive avec feedback visuel"),
        pageBreak(),

        // ═══════════════════════════════════════════════════════════════════════════
        // CHAPITRE 2
        // ═══════════════════════════════════════════════════════════════════════════
        h1("Chapitre 2 : Architecture et Technologies"),

        h2("2.1 Architecture Générale"),
        p("La plateforme suit une architecture client-serveur classique avec une séparation nette entre le frontend et le backend. L'architecture est conçue selon les principes de modularité et de séparation des responsabilités."),

        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [2200, 6826],
          rows: [
            new TableRow({ children: [
              new TableCell({ borders: borders(TEAL), width: { size: 2200, type: WidthType.DXA }, shading: { fill: TEAL, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 120, right: 120 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Couche", bold: true, color: WHITE, size: 20, font: "Arial" })] })] }),
              new TableCell({ borders: borders(TEAL), width: { size: 6826, type: WidthType.DXA }, shading: { fill: TEAL, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 120, right: 120 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Description", bold: true, color: WHITE, size: 20, font: "Arial" })] })] }),
            ]}),
            ...([
              ["Frontend (React)", "Application SPA développée avec React + Vite. Gère l'interface utilisateur, les formulaires, la visualisation des résultats et les appels API via Axios."],
              ["API Gateway (FastAPI)", "Serveur backend Python exposant des endpoints REST. Gère la validation des requêtes, le routing vers les services et la gestion des erreurs."],
              ["Module AutoML", "Service d'analyse de datasets, orchestration de l'agent LLM, entraînement des modèles ML, optimisation des hyperparamètres."],
              ["Module Migration", "Service d'analyse statique du code, appel LLM pour la migration, système de scoring, architecture multi-agents."],
              ["Mémoire Agent", "Système de mémoire persistante (JSON) permettant à l'agent de se souvenir des migrations précédentes et d'améliorer ses décisions."],
              ["LLM (GPT-4o)", "Modèle de langage d'OpenAI utilisé pour l'intelligence des deux modules. Accessible via l'API OpenAI."],
            ]).map((r, i) => new TableRow({ children: [
              new TableCell({ borders: borders("CCCCCC"), width: { size: 2200, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? "E8F5F3" : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: r[0], bold: true, size: 20, font: "Arial", color: TEAL })] })] }),
              new TableCell({ borders: borders("CCCCCC"), width: { size: 6826, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHTGRAY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: r[1], size: 20, font: "Arial", color: GRAY })] })] }),
            ]})),
          ],
        }),

        spacer(1),
        h2("2.2 Stack Technologique"),
        spacer(0),
        techTable([
          ["Backend", "Python 3.11", "Langage principal du serveur"],
          ["Backend", "FastAPI", "Framework API REST asynchrone"],
          ["Backend", "Uvicorn", "Serveur ASGI pour FastAPI"],
          ["Backend", "Pydantic v2", "Validation des données et schémas"],
          ["IA / ML", "OpenAI GPT-4o", "LLM pour AutoML et migration"],
          ["IA / ML", "scikit-learn", "Algorithmes de machine learning"],
          ["IA / ML", "Optuna", "Optimisation des hyperparamètres"],
          ["IA / ML", "pandas / numpy", "Manipulation et analyse des données"],
          ["Frontend", "React 18", "Framework UI composants"],
          ["Frontend", "Vite", "Bundler et dev server"],
          ["Frontend", "Axios", "Client HTTP pour les appels API"],
          ["Frontend", "Lucide React", "Bibliothèque d'icônes"],
          ["Frontend", "highlight.js", "Coloration syntaxique du code"],
          ["DevOps", "Git / GitHub", "Versioning et déploiement"],
          ["Tests Java", "Maven 3.9.6", "Build tool Java"],
          ["Tests Java", "JDK 21", "Runtime Java"],
          ["Tests Java", "SLF4J 2.0.9", "Logging Java"],
        ]),

        spacer(1),
        h2("2.3 Structure du Projet"),
        p("Le projet est organisé selon une structure claire séparant le backend et le frontend :"),
        spacer(0),
        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [3200, 5826],
          rows: [
            new TableRow({ children: [
              new TableCell({ borders: borders(TEAL), width: { size: 3200, type: WidthType.DXA }, shading: { fill: TEAL, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Chemin", bold: true, color: WHITE, size: 20, font: "Arial" })] })] }),
              new TableCell({ borders: borders(TEAL), width: { size: 5826, type: WidthType.DXA }, shading: { fill: TEAL, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Contenu", bold: true, color: WHITE, size: 20, font: "Arial" })] })] }),
            ]}),
            ...([
              ["backend/app/main.py", "Point d'entrée FastAPI, configuration des routers"],
              ["backend/app/migration/", "Service de migration, analyseurs, scorer, multi-agent"],
              ["backend/app/automl/service/", "Services AutoML : agent, données, entraînement, évaluation"],
              ["backend/app/agent/memory.py", "Système de mémoire persistante de l'agent"],
              ["backend/data/uploads/", "Fichiers uploadés par les utilisateurs"],
              ["backend/data/migrated/", "Fichiers Java/Python migrés"],
              ["frontend/src/pages/migration/", "Interface migration (MigrationHome.jsx)"],
              ["frontend/src/pages/automl/", "Pages AutoML (Upload, Train, Agent, Results...)"],
              ["frontend/src/services/", "Services Axios (migrationService.js, automlService.js)"],
              ["frontend/src/components/", "Composants réutilisables (AutoMLStepBar, etc.)"],
            ]).map((r, i) => new TableRow({ children: [
              new TableCell({ borders: borders("CCCCCC"), width: { size: 3200, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? "E8F5F3" : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: r[0], size: 19, font: "Courier New", color: TEAL })] })] }),
              new TableCell({ borders: borders("CCCCCC"), width: { size: 5826, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHTGRAY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: r[1], size: 20, font: "Arial", color: GRAY })] })] }),
            ]})),
          ],
        }),
        pageBreak(),

        // ═══════════════════════════════════════════════════════════════════════════
        // CHAPITRE 3
        // ═══════════════════════════════════════════════════════════════════════════
        h1("Chapitre 3 : Module AutoML Agentique"),

        h2("3.1 Vue d'ensemble"),
        p("Le module AutoML est le cœur de la plateforme. Il permet à des utilisateurs sans expertise en machine learning de créer des modèles prédictifs performants en quelques clics. L'agent GPT-4o joue un rôle central en analysant le dataset et en orchestrant toutes les étapes du pipeline."),

        h2("3.2 Architecture du Module AutoML"),
        p("Le module AutoML est organisé en plusieurs couches de services :"),
        bullet("data_service.py : Chargement, validation et prévisualisation des datasets CSV"),
        bullet("agent_service.py : Orchestration de l'agent LLM pour l'analyse et la planification"),
        bullet("preprocessing_service.py : Nettoyage et transformation des données"),
        bullet("training_service.py : Entraînement multi-modèles avec optimisation Optuna"),
        bullet("evaluation_service.py : Évaluation et métriques des modèles entraînés"),
        bullet("llm_service.py : Interface avec l'API OpenAI"),
        bullet("action_executor_service.py : Exécution des actions de nettoyage planifiées"),

        h2("3.3 Modes de Fonctionnement"),
        h3("3.3.1 Mode Manuel"),
        p("Le mode manuel permet à l'utilisateur de contrôler entièrement les étapes du pipeline ML. L'interface propose une barre de progression en 4 étapes (Mode → Upload → Pipeline → Résultats) et un formulaire de configuration détaillé."),

        h3("3.3.2 Mode Agent"),
        p("Le mode agent délègue toutes les décisions à l'agent GPT-4o. L'agent exécute une chaîne d'actions (\"tool calls\") structurée :"),
        spacer(0),
        twoColTable([
          ["Étape 1 : analyze_dataset", "L'agent analyse chaque colonne du dataset : types, valeurs nulles, min/max/moyenne, outliers (méthode IQR), asymétrie, valeurs top"],
          ["Étape 2 : decide_plan", "L'agent génère un plan de nettoyage et d'ingénierie de features adapté, sélectionne les modèles ML et configure Optuna"],
          ["Étape 3 : apply_cleaning", "Exécution des actions de nettoyage : suppression/imputation des nulls, suppression des doublons, suppression des outliers"],
          ["Étape 4 : apply_features", "Ingénierie de features : encodage des variables catégorielles, normalisation, création de nouvelles features"],
          ["Étape 5 : train_models", "Entraînement des modèles sélectionnés avec optimisation des hyperparamètres par Optuna"],
          ["Étape 6 : evaluate", "Évaluation comparative des modèles : accuracy, F1-score, precision, recall, AUC-ROC"],
        ], 2800),

        spacer(1),
        h2("3.4 Rapport de l'Agent"),
        p("Le module génère un rapport détaillé de toutes les actions effectuées par l'agent, organisé en 3 sections :"),
        bullet("Section R1 — Analyse du dataset : tableau des colonnes avec type, nulls, min/max/moyenne, outliers (bornes IQR), asymétrie"),
        bullet("Section R2 — Plan de l'agent : source de décision, confiance, modèles sélectionnés, actions de nettoyage et d'ingénierie, avertissements"),
        bullet("Section R3 — Exécution du nettoyage : shape avant/après, lignes supprimées, détail des actions (statut, colonnes, lignes affectées)"),

        h2("3.5 Algorithmes Supportés"),
        spacer(0),
        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [2500, 2263, 4263],
          rows: [
            new TableRow({ children: [
              new TableCell({ borders: borders(TEAL), width: { size: 2500, type: WidthType.DXA }, shading: { fill: TEAL, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Algorithme", bold: true, color: WHITE, size: 20, font: "Arial" })] })] }),
              new TableCell({ borders: borders(TEAL), width: { size: 2263, type: WidthType.DXA }, shading: { fill: TEAL, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Type", bold: true, color: WHITE, size: 20, font: "Arial" })] })] }),
              new TableCell({ borders: borders(TEAL), width: { size: 4263, type: WidthType.DXA }, shading: { fill: TEAL, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Hyperparamètres Optuna", bold: true, color: WHITE, size: 20, font: "Arial" })] })] }),
            ]}),
            ...([
              ["Random Forest", "Classification/Régression", "n_estimators, max_depth, min_samples_split"],
              ["Gradient Boosting", "Classification/Régression", "n_estimators, learning_rate, max_depth"],
              ["XGBoost", "Classification/Régression", "n_estimators, learning_rate, max_depth, subsample"],
              ["SVM", "Classification", "C, kernel, gamma"],
              ["Logistic Regression", "Classification", "C, solver, max_iter"],
              ["KNN", "Classification", "n_neighbors, weights, metric"],
              ["Decision Tree", "Classification/Régression", "max_depth, min_samples_split, criterion"],
              ["MLP (Neural Net)", "Classification", "hidden_layer_sizes, activation, alpha"],
            ]).map((r, i) => new TableRow({ children: [
              new TableCell({ borders: borders("CCCCCC"), width: { size: 2500, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? "E8F5F3" : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: r[0], bold: true, size: 20, font: "Arial", color: DARK })] })] }),
              new TableCell({ borders: borders("CCCCCC"), width: { size: 2263, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHTGRAY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: r[1], size: 20, font: "Arial", color: GRAY })] })] }),
              new TableCell({ borders: borders("CCCCCC"), width: { size: 4263, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHTGRAY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: r[2], size: 20, font: "Arial", color: GRAY })] })] }),
            ]})),
          ],
        }),

        spacer(1),
        h2("3.6 Interface Utilisateur AutoML"),
        p("L'interface AutoML est organisée autour d'une barre de progression en 4 étapes communes :"),
        bullet("Étape 1 — Mode : Choix entre mode Manuel ou Agent LLM"),
        bullet("Étape 2 — Upload : Chargement du dataset CSV avec prévisualisation des 5 premières lignes"),
        bullet("Étape 3 — Pipeline : Configuration du pipeline (mode manuel) ou lancement de l'agent (mode agent)"),
        bullet("Étape 4 — Résultats : Tableau comparatif des modèles, métriques, rapport détaillé, interface de prédiction"),

        pageBreak(),

        // ═══════════════════════════════════════════════════════════════════════════
        // CHAPITRE 4
        // ═══════════════════════════════════════════════════════════════════════════
        h1("Chapitre 4 : Module de Migration de Code"),

        h2("4.1 Vue d'ensemble"),
        p("Le module de migration de code assiste les développeurs dans la modernisation de leur code Java et Python legacy. Il utilise un pipeline LLM enrichi d'une architecture multi-agents pour garantir la qualité du code migré."),

        h2("4.2 Langages et Versions Supportés"),
        spacer(0),
        twoColTable([
          ["Java 8", "Lambdas, Stream API, Optional, java.time, default methods"],
          ["Java 11", "var, String.strip()/isBlank()/lines(), HTTP Client"],
          ["Java 17", "Records, Sealed classes, Pattern matching instanceof, Switch expressions, Text blocks"],
          ["Java 21", "Virtual threads, Sequenced collections, Record patterns, Switch pattern matching"],
          ["Python 3.8", "Walrus operator :=, f-strings, typing module, pathlib, dataclasses"],
          ["Python 3.10", "match/case (pattern matching), parenthesized context managers, better error messages"],
          ["Python 3.12", "type aliases (type X = Y), @override decorator, improved f-strings, better performance"],
        ]),

        spacer(1),
        h2("4.3 Modes de Migration"),
        h3("4.3.1 Mode Standard"),
        p("Migration directe via un seul appel LLM. L'analyseur statique identifie les problèmes, le prompt est enrichi avec ces informations, et GPT-4o génère le code migré. C'est le mode le plus rapide."),

        h3("4.3.2 Mode Réflexion (Agentique)"),
        p("L'agent migre le code, puis analyse son propre résultat. S'il reste des problèmes non résolus, il reçoit un feedback explicite et se corrige. Ce cycle peut se répéter jusqu'à 3 fois (configurable entre 1 et 5). Un système de mémoire persistante permet à l'agent de s'améliorer au fil des migrations."),

        h3("4.3.3 Mode Multi-Agents"),
        p("Pipeline de 3 agents coordonnés par un orchestrateur :"),
        spacer(0),
        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [2000, 2500, 4526],
          rows: [
            new TableRow({ children: [
              new TableCell({ borders: borders(TEAL), width: { size: 2000, type: WidthType.DXA }, shading: { fill: TEAL, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Agent", bold: true, color: WHITE, size: 20, font: "Arial" })] })] }),
              new TableCell({ borders: borders(TEAL), width: { size: 2500, type: WidthType.DXA }, shading: { fill: TEAL, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Rôle", bold: true, color: WHITE, size: 20, font: "Arial" })] })] }),
              new TableCell({ borders: borders(TEAL), width: { size: 4526, type: WidthType.DXA }, shading: { fill: TEAL, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Actions", bold: true, color: WHITE, size: 20, font: "Arial" })] })] }),
            ]}),
            ...([
              ["AnalyzerAgent", "Analyste sémantique", "Enrichit l'analyse statique avec des insights de complexité, de patterns et de risques"],
              ["MigratorAgent", "Migrateur principal", "Migre le code en tenant compte de l'analyse enrichie et de la mémoire des migrations passées"],
              ["VerifierAgent", "Vérificateur qualité", "Évalue la qualité de la migration, détecte les régressions et décide si un retraitement est nécessaire"],
            ]).map((r, i) => new TableRow({ children: [
              new TableCell({ borders: borders("CCCCCC"), width: { size: 2000, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? "E8F5F3" : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: r[0], bold: true, size: 20, font: "Arial", color: TEAL })] })] }),
              new TableCell({ borders: borders("CCCCCC"), width: { size: 2500, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHTGRAY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: r[1], size: 20, font: "Arial", color: GRAY })] })] }),
              new TableCell({ borders: borders("CCCCCC"), width: { size: 4526, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHTGRAY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: r[2], size: 20, font: "Arial", color: GRAY })] })] }),
            ]})),
          ],
        }),

        spacer(1),
        h2("4.4 Système de Scoring"),
        p("Un système de scoring de qualité évalue le code avant et après migration sur une échelle de 0 à 100 :"),
        spacer(0),
        twoColTable([
          ["Score 90-100 (A)", "Excellent — Low risk — Code moderne et bien structuré"],
          ["Score 75-89 (B)", "Bon — Medium risk — Quelques améliorations mineures possibles"],
          ["Score 60-74 (C)", "Moyen — Medium risk — Plusieurs problèmes à corriger"],
          ["Score 40-59 (D)", "Faible — High risk — Nombreux problèmes détectés"],
          ["Score 0-39 (F)", "Critique — Critical risk — Code legacy avec de nombreuses mauvaises pratiques"],
        ]),
        spacer(1),
        p("Les pénalités sont appliquées selon la sévérité des problèmes : -15 pts (Critical), -8 pts (High), -4 pts (Medium), -2 pts (Low). Des bonus sont accordés pour les bonnes pratiques modernes : +5 pts (lambdas/streams/records), +3 pts (Optional/generics)."),

        h2("4.5 Analyse Statique"),
        p("L'analyseur statique (analyzer.py pour Java, python_analyzer.py pour Python) détecte 20+ types de problèmes :"),
        h3("Problèmes Java détectés"),
        bullet("Raw types sans generics (HashMap, List, ArrayList sans paramètres de type)"),
        bullet("Utilisation de java.util.Date (deprecated depuis Java 8)"),
        bullet("e.printStackTrace() au lieu de logging structuré"),
        bullet("String concatenation dans les boucles (performance)"),
        bullet("== sur les String au lieu de .equals()"),
        bullet("Resource leaks (FileWriter, Connection non fermés)"),
        bullet("catch(Exception e) générique au lieu d'exceptions spécifiques"),
        bullet("Cast dangereux sans vérification instanceof"),
        bullet("Boucles for(int i=0...) old-style"),
        bullet("Constantes mal déclarées (sans static final)"),
        h3("Problèmes Python détectés"),
        bullet("bare except: qui avale toutes les erreurs"),
        bullet("open() sans context manager (with statement)"),
        bullet("print() au lieu de logging"),
        bullet("Comparaison avec == None au lieu de is None"),
        bullet("Absence de type hints"),
        bullet("Absence de docstrings"),
        bullet("range(len()) au lieu de for-each direct"),
        bullet("Concatenation de strings avec + en boucle"),

        h2("4.6 Interface Utilisateur Migration"),
        p("L'interface de migration est accessible via le menu de navigation. Elle propose :"),
        bullet("Une barre de progression en 4 étapes : Upload → Analyse → Migration → Résultats"),
        bullet("Une zone de drop (drag & drop) pour l'upload des fichiers Java ou Python"),
        bullet("La sélection du mode de migration (Standard / Réflexion / Multi-Agents)"),
        bullet("La sélection de la version cible avec description des nouvelles fonctionnalités"),
        bullet("Un tableau de bord de résultats avec les rings de score avant/après"),
        bullet("Les métriques détaillées du code (lignes, classes, méthodes, imports, etc.)"),
        bullet("Un tableau de bord des modifications avec vue avant/après pour chaque changement"),
        bullet("Un visualiseur de code avec coloration syntaxique (highlight.js)"),
        bullet("Le téléchargement du fichier migré"),
        pageBreak(),

        // ═══════════════════════════════════════════════════════════════════════════
        // CHAPITRE 5
        // ═══════════════════════════════════════════════════════════════════════════
        h1("Chapitre 5 : Implémentation et Tests"),

        h2("5.1 Environnement de Développement"),
        spacer(0),
        twoColTable([
          ["Système d'exploitation", "Windows 11"],
          ["IDE", "VS Code avec extensions Java, Python, ESLint"],
          ["Python", "3.11 (Anaconda)"],
          ["Node.js", "18.x (npm)"],
          ["Java", "JDK 21 (Microsoft OpenJDK)"],
          ["Maven", "3.9.6"],
          ["Navigateur de test", "Microsoft Edge, Google Chrome"],
          ["Versioning", "Git / GitHub"],
          ["API LLM", "OpenAI GPT-4o via API key"],
        ]),

        spacer(1),
        h2("5.2 Tests du Module AutoML"),
        h3("5.2.1 Dataset de test"),
        p("Nous avons créé un dataset de test (test_dataset_errors.csv) contenant 100 lignes et 7 colonnes avec des erreurs intentionnelles : valeurs nulles dans Age et Salary, valeurs aberrantes (Age=-5, Age=850, Salary=-3000, Salary=999999), lignes dupliquées, et incohérences de casse (IT/it, LYON/Lyon)."),

        h3("5.2.2 Résultats des tests AutoML"),
        spacer(0),
        twoColTable([
          ["Analyse du dataset", "Détection correcte des 7 colonnes, types, statistiques, 15 outliers détectés par IQR"],
          ["Plan de l'agent", "Sélection automatique de Random Forest comme modèle principal, stratégie d'imputation par médiane, encodage one-hot pour les catégorielles"],
          ["Nettoyage", "Suppression de 3 doublons, imputation de 8 valeurs nulles, suppression de 12 outliers"],
          ["Entraînement", "3 modèles entraînés (Random Forest, Gradient Boosting, Logistic Regression), 50 trials Optuna"],
          ["Meilleur modèle", "Random Forest : Accuracy 87.5%, F1-Score 0.86, AUC-ROC 0.91"],
        ]),

        spacer(1),
        h2("5.3 Tests du Module Migration"),
        h3("5.3.1 Fichiers de test créés"),
        p("Nous avons créé plusieurs fichiers de test avec des problèmes intentionnels :"),
        bullet("UserService.java : 6 problèmes détectés (raw types, Date deprecated, e.printStackTrace, FileWriter leak, boucles old-style)"),
        bullet("LegacyOrderService.java : 13 problèmes (raw types, constante mal déclarée, == sur String, cast dangereux, synchronized inutile...)"),
        bullet("BankAccountService.java : 10 problèmes (raw types, Date, String concat, bare except Python équivalent...)"),
        bullet("legacy_data_processor.py : 12 problèmes Python (bare except, open sans with, print, == None, pas de type hints...)"),

        h3("5.3.2 Résultats des migrations"),
        spacer(0),
        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [2800, 1400, 1400, 1400, 2026],
          rows: [
            new TableRow({ children: [
              ["Fichier", 2800], ["Score Avant", 1400], ["Score Après", 1400], ["Amélioration", 1400], ["Problèmes corrigés", 2026]
            ].map(([t, w]) => new TableCell({ borders: borders(TEAL), width: { size: w, type: WidthType.DXA }, shading: { fill: TEAL, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 80, right: 80 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: t, bold: true, color: WHITE, size: 18, font: "Arial" })] })] })) }),
            ...([
              ["UserService.java", "0 / F", "100 / A", "+100 pts", "6/6 (100%)"],
              ["LegacyOrderService.java", "0 / F", "100 / A", "+100 pts", "19/19 (100%)"],
              ["BankAccountService.java", "0 / F", "100 / A", "+100 pts", "14/14 (100%)"],
              ["legacy_data_processor.py", "15 / F", "95 / A", "+80 pts", "11/12 (92%)"],
            ]).map((r, i) => new TableRow({ children: [
              new TableCell({ borders: borders("CCCCCC"), width: { size: 2800, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? "E8F5F3" : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 80, right: 80 }, children: [new Paragraph({ children: [new TextRun({ text: r[0], size: 19, font: "Courier New", color: TEAL })] })] }),
              new TableCell({ borders: borders("CCCCCC"), width: { size: 1400, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHTGRAY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 80, right: 80 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: r[1], size: 20, font: "Arial", color: "#ef4444" })] })] }),
              new TableCell({ borders: borders("CCCCCC"), width: { size: 1400, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHTGRAY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 80, right: 80 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: r[2], size: 20, font: "Arial", color: TEAL })] })] }),
              new TableCell({ borders: borders("CCCCCC"), width: { size: 1400, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHTGRAY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 80, right: 80 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: r[3], bold: true, size: 20, font: "Arial", color: TEAL })] })] }),
              new TableCell({ borders: borders("CCCCCC"), width: { size: 2026, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHTGRAY : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 80, right: 80 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: r[4], size: 20, font: "Arial", color: GRAY })] })] }),
            ]})),
          ],
        }),

        spacer(1),
        h3("5.3.3 Validation avec Maven"),
        p("Les fichiers Java migrés ont été compilés et exécutés avec succès via Maven 3.9.6 + JDK 21 :"),
        bullet("mvn compile : BUILD SUCCESS pour LegacyOrderService et BankAccountService"),
        bullet("mvn exec:java : Exécution correcte avec logs SLF4J structurés"),
        bullet("Vérification de la préservation de la logique métier (mêmes résultats de calcul)"),
        bullet("Vérification de la présence du package Java dans le code migré"),

        h2("5.4 Corrections et Améliorations Apportées"),
        p("Suite aux tests, plusieurs corrections ont été apportées :"),
        bullet("Fix du rechargement automatique uvicorn lors de l'upload de fichiers .py (extension .upload)"),
        bullet("Préservation automatique de la déclaration package Java dans le code migré"),
        bullet("Correction du format des appels logging Python (f-strings au lieu de logging.error('msg:', e))"),
        bullet("Ajout de logging.basicConfig() automatique dans les migrations Python"),
        bullet("Préservation des blocs try/except lors de la migration Python"),
        bullet("Création d'un dossier temporaire avec fichiers de test lors de l'exécution"),
        pageBreak(),

        // ═══════════════════════════════════════════════════════════════════════════
        // CONCLUSION
        // ═══════════════════════════════════════════════════════════════════════════
        h1("Conclusion et Perspectives"),

        h2("Bilan du Projet"),
        p("Ce projet de fin d'études a permis de développer une plateforme IA complète et fonctionnelle intégrant deux modules innovants. Les principaux objectifs ont été atteints :"),
        bullet("Un module AutoML agentique opérationnel permettant de créer des pipelines ML automatiquement"),
        bullet("Un module de migration de code Java et Python avec des taux de correction proches de 100%"),
        bullet("Une interface web moderne et intuitive avec une expérience utilisateur soignée"),
        bullet("Une architecture multi-agents robuste avec système de mémoire persistante"),
        bullet("Un système de scoring de qualité du code transparent et explicite"),
        bullet("Des tests complets validant le bon fonctionnement de toutes les fonctionnalités"),

        h2("Difficultés Rencontrées"),
        bullet("Gestion de la cohérence des réponses du LLM (format JSON, préservation du package Java, logging Python)"),
        bullet("Problème de rechargement automatique d'uvicorn lors de l'upload de fichiers Python"),
        bullet("Configuration de l'environnement Java (JAVA_HOME, Maven PATH) sous Windows"),
        bullet("Gestion des dépendances externes dans les fichiers Java migrés (SQLException, SLF4J)"),
        bullet("Calibration du système de scoring pour refléter fidèlement la qualité du code"),

        h2("Perspectives et Améliorations Futures"),
        bullet("Support de nouveaux langages : TypeScript, C#, Kotlin"),
        bullet("Intégration d'une base de données pour persister les datasets et résultats"),
        bullet("Ajout d'un module de détection d'anomalies et de séries temporelles dans AutoML"),
        bullet("Implémentation d'un système de tests unitaires automatiques générés par LLM"),
        bullet("Création d'une API publique pour l'intégration dans des pipelines CI/CD"),
        bullet("Mode batch pour la migration de projets entiers (multiples fichiers)"),
        bullet("Dashboard d'administration pour surveiller les performances et les coûts API"),
        bullet("Fine-tuning d'un modèle spécialisé en migration de code pour réduire les coûts LLM"),

        spacer(1),
        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [9026],
          rows: [new TableRow({ children: [new TableCell({
            borders: borders(TEAL),
            width: { size: 9026, type: WidthType.DXA },
            shading: { fill: "E8F5F3", type: ShadingType.CLEAR },
            margins: { top: 200, bottom: 200, left: 240, right: 240 },
            children: [
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\"L'intelligence artificielle n'est pas là pour remplacer les développeurs,", size: 22, italics: true, color: DARK, font: "Arial" })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "mais pour les rendre plus efficaces et les libérer des tâches répétitives.\"", size: 22, italics: true, color: DARK, font: "Arial" })] }),
            ],
          })]})]
        }),
        pageBreak(),

        // ═══════════════════════════════════════════════════════════════════════════
        // BIBLIOGRAPHIE
        // ═══════════════════════════════════════════════════════════════════════════
        h1("Bibliographie et Webographie"),

        h2("Documentation Officielle"),
        bullet("FastAPI Documentation — https://fastapi.tiangolo.com"),
        bullet("React Documentation — https://react.dev"),
        bullet("OpenAI API Documentation — https://platform.openai.com/docs"),
        bullet("scikit-learn User Guide — https://scikit-learn.org/stable/user_guide.html"),
        bullet("Optuna Documentation — https://optuna.readthedocs.io"),
        bullet("Apache Maven Documentation — https://maven.apache.org/guides"),
        bullet("SLF4J Documentation — https://www.slf4j.org/manual.html"),

        h2("Articles et Ressources"),
        bullet("Hutter, F., Kotthoff, L., Vanschoren, J. (2019). Automated Machine Learning: Methods, Systems, Challenges. Springer."),
        bullet("Feurer, M., Klein, A., Eggensperger, K. et al. (2015). Efficient and Robust Automated Machine Learning. NIPS 2015."),
        bullet("Brown, T. et al. (2020). Language Models are Few-Shot Learners (GPT-3). NeurIPS 2020."),
        bullet("Akiba, T. et al. (2019). Optuna: A Next-generation Hyperparameter Optimization Framework. KDD 2019."),
        bullet("Pedregosa, F. et al. (2011). Scikit-learn: Machine Learning in Python. JMLR 12, pp. 2825-2830."),

        h2("Outils et Technologies"),
        bullet("GitHub Repository — https://github.com/bassma-20/pfe-ai-platform"),
        bullet("highlight.js — Syntax Highlighting — https://highlightjs.org"),
        bullet("Lucide React Icons — https://lucide.dev"),
        bullet("Vite Build Tool — https://vitejs.dev"),
        bullet("Microsoft JDK 21 — https://www.microsoft.com/openjdk"),
      ],
    },
  ],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("C:\\Users\\hello\\Documents\\projet pfe\\Rapport_PFE_Ahmed_Bassma.docx", buffer);
  console.log("✅ Rapport généré : Rapport_PFE_Ahmed_Bassma.docx");
}).catch(err => {
  console.error("❌ Erreur:", err);
  process.exit(1);
});
