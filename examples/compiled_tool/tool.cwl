baseCommand: notebookTool
class: CommandLineTool
cwlVersion: v1.1
hints:
  DockerRequirement:
    dockerImageId: jn2cwl:latest
inputs:
  dataset:
    inputBinding:
      prefix: --dataset
    type: File
outputs:
  after_transform_data:
    outputBinding:
      glob: new_data.png
    type: File
  original_image:
    outputBinding:
      glob: original_data.png
    type: File
