SPEC

# xdrs-compiler

This tool compiles a bunch of documents in a source folder to xdrs scopes so that LLMs can more easily consume them as policies.

## Getting Started

```sh
xdrs-compiler --input-dir mydir --xdrs-root .xdrs --scope myscope
```

In this example, it will traverse all dirs in mydir folder, open all supported files (.md, pdf, word, etc), extract their text and convert all of its content that looks like policies into the xdrs scope "myscope" in dir .xdrs.

## How it works

The compile process is performed in four key phases

### 1-Preparation
  Objective: Have a normalised input file structure to work with
  1. Read all input files that will be used in input dir
  2. Convert those files to .md files using the same folder tree (with markitdown)
  3. Remove files that have less than 10 words in content

### 2-Analysis
  Objective: Plan target xdrs structure
  1. Analyse each doc and identify topics with potential to become policies or skills along with a date the content was produced (if possible)
     - e.g.: 
     ```json
     {
        "[full/path/of/source/file]": {
            "date": "[potential date the document was produced. ISO format]",
            "abstract": "[summary of the document contents focused on problem statement and decision/outcomes. <30 words]",
            "topic_policies": [
                "[topic title with potential to become a policy. <10 words]"
            ],
            "topic_skills": [
                "[topic title with potential to become a skill. <10 words]"
            ]
        },
        "mydir/2021/presentation.pdf.md": {
            "date": "2019-01-01",
            "abstract": "This presentation discuss about the latest statistics on our call center along with some tips",
            "topic_policies": [
                "required behaviors while talking to customers",
            ],
            "topic_skills": [
                "detailed call center procedures",
            ]
        },
        "mydir/francesca/notes.txt": {
            "abstract": "meeting notes about what we need to check during tests",
            "topic_policies": [
                "minimum items to check while testing customer apps"
            ]
        },
        "mydir/emails/2024-02-12-regulations-memo.txt": {
            "abstract": "email from anderson to myrthe about new regulations to follow",
            "topic_policies": [
                "requirement to follow regulation ABCD-123 during production deployments for customer apps"
            ]
        }
     }
  2. From the list of topics, propose a list of policies and skills that will be created in xdrs scope
  ```json
    "proposed_policies": {
        "[title of the policy]": {
            "abstract": "[summary of what this policy/skill is about. <20 words]",
            "related_docs": [
                "[doc path that contains meaningful content for this policy]"
            ]
        },
        "production-deployments-requirements": {
            "abstract": "Defines what are the minimum requirements for prd deployments",
            "related_docs": [
                "mydir/francesca/notes.txt",
                "mydir/emails/2024-02-12-regulations-memo.txt"
            ],
        },
        "call-center-expected-behaviors": {
            "abstract": "Behaviors expected from agents while picking up phone calls",
            "related_docs": [
                "mydir/2021/presentation.pdf.md"
            ]
        }
    },
    "proposed_skills": {
        "call-center-procedures": {
            "abstract": "Defines a set of steps to follow as you pick up the phone with a customer",
            "related_docs": [
                "mydir/2021/presentation.pdf.md"
            ]
        }
    }
  ```

## 3-Synthesis
  Objective: Generate policies and skills according to the proposed list
  1. For each proposal, write a xdrs element using write-policy/write-skill skill. Create a prompt inputing:
  ```json
    {
        "type": "skill",
        "title": "call-center-procedures",
        "abstract": "Defines a set of steps to follow as you pick up the phone with a customer",
        "related_docs": [
            "mydir/2021/presentation.pdf.md"
        ],
        "related_topics": [
            "detailed call center procedures"
        ]
    }
  ```
  2. After all docs are created, run review skill in each generated doc and fix issues
