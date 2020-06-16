#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: CommandLineTool

requirements:
  InlineJavascriptRequirement: {}
  ResourceRequirement:
    coresMax: 1
    ramMin: 100  # just a default, could be lowered

hints:
  DockerRequirement:
    dockerImageId: jn2cwl:latest
    dockerFile:
      $include: 'Dockerfile'

inputs:
  data:
    type: File
    inputBinding:
      position: 1

baseCommand: [ 'python', '/app/app.py' ]

outputs: []
$namespaces:
  s: https://schema.org/
s:license: https://spdx.org/licenses/Apache-2.0