
## v0.2.x

Base communication, permissions, security, distribution.

------

### Please Try

Please try the following and report any issues.

#### Workflows
- installation
- store distribution
- admin permissions

##### 1. Installation
- download Spore OS
- follow installation instructions in the zipped readme
- in terminal:
    - open witness: `spore open witness`
    - open shell: `spore open shell`
    - get list of nodes `spore hint body=""`
- in shell:
    - get list of nodes `hint body=""`, see the results in shell and witness

##### 2. Store Distribution
- in spore-shell:
    - refresh store `store.refresh`
    - browse store for alias `store.browse`
    - install alias `store.get node=alias | install`

##### 3. Admin Permissions
- prompts should occur when trying to install a node `store.get node=alias | install` or uninstall `uninstall node=alias`
- try accepting and denying these prompts
