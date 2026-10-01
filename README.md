# TsekMate
### Grade less. Know more.

TsekMate is an AI grading assistant for teachers. It provides a first-pass assessment of student work using the teacher's instructions and rubric, then allows the teacher to review, edit, and approve the results.

> **The AI assists with grading. The teacher makes the final decision.**

---

## About TsekMate

TsekMate is designed to help teachers grade open-ended student work such as short answers, essays, and performance tasks.

The system can analyze typed or handwritten student work and provide:

- A score for each rubric criterion
- Evidence from the student's answer
- A short feedback comment
- A confidence level
- Flags for results that may need additional review

After grading, TsekMate can also identify class-wide learning gaps and generate a short reteaching activity based on the weakest area.

---

## Getting Started

### 1. Open TsekMate

Open the application through the provided project/demo link.

If running the project locally, follow the installation instructions in the project repository.

### 2. Create an activity

Before uploading student work, provide the following:

- **Task instructions** – What students were asked to do
- **Rubric** – The criteria and points used for grading
- **Grade level** – The intended student level
- **Subject** – The subject or course
- **Answer key** *(optional)* – Expected answers or solutions
- **Additional notes** *(optional)* – Special grading instructions, such as accepting answers in Filipino

Make sure the rubric is complete before proceeding to grading.

### 3. Upload student work

Upload the student's work or take a photo of the handwritten response.

TsekMate supports:

- Typed responses
- Handwritten responses
- Image-based submissions

For better results, make sure uploaded images are clear and readable.

### 4. Review the AI-generated grade

After processing, TsekMate displays the suggested grade for each rubric criterion.

Each result includes:

**Score**  
The points suggested for the criterion.

**Evidence**  
The portion of the student's response used to support the score.

**Feedback**  
A short explanation of the assessment.

**Confidence**  
An indication of how confident the system is in the suggested score.

### 5. Check flagged results

Low-confidence results and disagreements from the second AI review are highlighted for additional attention.

Review these results before approving the submission.

### 6. Edit the results

Teachers can modify:

- Scores
- Feedback
- Other grading details

The teacher should verify the AI's suggestions against the student's actual work and the original rubric.

### 7. Approve the grade

Once the teacher is satisfied with the assessment, approve the final grade.

> TsekMate does not independently finalize grades. Final grading decisions remain with the teacher.

---

## View Class Learning Insights

After multiple submissions have been graded, open the **Class Knowledge Map**.

The knowledge map summarizes areas where students may have struggled, such as:

- Specific rubric criteria
- Concepts
- Common mistakes
- Areas requiring additional instruction

Use these results as a guide for identifying topics that may need to be revisited.

---

## Generate a Reteaching Activity

After reviewing the Class Knowledge Map:

1. Identify the weakest concept or criterion.
2. Select the reteaching option.
3. Review the generated activity.
4. Modify it if necessary.
5. Use the activity as a starting point for classroom instruction.

The generated activity is intended to support the teacher's planning rather than replace it.

---

## Export Grades

After reviewing and approving the grades, use the export option to create a class record.

Supported formats:

- **CSV**
- **Excel**

Only export grades after completing the teacher review process.

---

## Recommended Workflow

For the intended TsekMate workflow, follow this sequence:

```text
Create Activity
      ↓
Add Instructions & Rubric
      ↓
Upload Student Work
      ↓
AI Processes Submission
      ↓
Review Scores & Evidence
      ↓
Check Low-Confidence Results
      ↓
Edit if Necessary
      ↓
Approve Final Grade
      ↓
View Class Knowledge Map
      ↓
Generate Reteaching Activity
      ↓
Export Grades
