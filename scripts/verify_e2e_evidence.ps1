param(
    [string]$RunDirectory = "data/e2e-20261010-01",
    [string]$CandidateDirectory = "data/assessment-reference-candidates/walkthroughs"
)

# Offline verification of evidence captured by the real browser/API flow.
# Does not call AWS, send assessments, alter saved attempts, or publish drafts.
$ErrorActionPreference = 'Stop'
$session = Get-Content (Join-Path $RunDirectory 'session.json') -Raw | ConvertFrom-Json
if (-not $session -or -not $session.PSObject.Properties['scope']) {
    throw 'Evidence is empty or incomplete. Run offline after stopping the local E2E server.'
}
$failures = [System.Collections.Generic.List[string]]::new()
$results = [System.Collections.Generic.List[object]]::new()
function Check([bool]$Condition, [string]$Message) {
    if (-not $Condition) { $failures.Add($Message) }
}

Check ($session.awsWrites -eq 0) 'Isolation: unexpected AWS writes'
Check ($session.humanLabelsApproved -eq $false) 'Draft fixtures must not be represented as human-approved'

foreach ($file in Get-ChildItem $CandidateDirectory -Filter '*.json') {
    $guide = Get-Content $file.FullName -Raw | ConvertFrom-Json
    $problemId = $file.BaseName
    $request = @($session.assessmentInputs | Where-Object { $_.problem.id -eq $problemId })[0]
    $review = @($session.assessmentOutputs | Where-Object { $_.problem_id -eq $problemId -and $_.source -eq 'ai' })[0]
    $attempt = @($session.attempts | Where-Object { $_.problemId -eq $problemId })[0]
    Check ($null -ne $request -and $null -ne $attempt) "$problemId`: browser submission/save evidence missing"
    Check ($null -ne $review) "$problemId`: no accepted AI review (unavailable is not a successful score)"
    if (-not $request -or -not $attempt) { continue }

    $components = @($guide.steps | Where-Object type -eq 'add_component')
    $connections = @($guide.steps | Where-Object type -eq 'add_connection')
    $actions = @($guide.steps | Where-Object { $_.type -in 'add_component', 'add_connection' -or $_.componentUpdate })
    Check ($request.components.Count -eq $components.Count) "$problemId`: submitted component count differs from guide"
    Check ($request.connections.Count -eq $connections.Count) "$problemId`: submitted connection count differs from guide"
    Check ($attempt.nodes.Count -eq $components.Count -and $attempt.edges.Count -eq $connections.Count) "$problemId`: saved canvas counts differ"
    if ($review) {
        Check ($review.overall_score -ge 95 -and $review.score_available -eq $true -and $review.verdict -eq 'strong_alignment') "$problemId`: reference acceptance failed (score $($review.overall_score), verdict $($review.verdict))"
        Check ($review.requirement_revision -eq $request.problem.requirementRevision) "$problemId`: review/request revision mismatch"
    }
    Check ($attempt.problemRequirementSpec.revision -eq $request.problem.requirementRevision) "$problemId`: saved requirements revision mismatch"

    foreach ($componentStep in $components) {
        $actual = @($request.components | Where-Object id -eq $componentStep.component.nodeId)[0]
        Check ($null -ne $actual) "$problemId`: component missing $($componentStep.component.nodeId)"
        $expected = @{}
        foreach ($property in $componentStep.component.properties.PSObject.Properties) { $expected[$property.Name] = $property.Value }
        # Known schemas migrate description to purpose; provider metadata with no
        # purpose field may preserve description. Check the value in either case.
        if ($expected.ContainsKey('description') -and -not $actual.properties.PSObject.Properties['description']) {
            if (-not $expected.ContainsKey('purpose')) { $expected['purpose'] = $expected['description'] }
            $expected.Remove('description')
        }
        foreach ($update in $guide.steps | Where-Object { $_.componentUpdate.nodeId -eq $componentStep.component.nodeId }) {
            foreach ($property in $update.componentUpdate.properties.PSObject.Properties) { $expected[$property.Name] = $property.Value }
        }
        foreach ($key in $expected.Keys) {
            $left = $actual.properties.$key | ConvertTo-Json -Depth 20 -Compress
            $right = $expected[$key] | ConvertTo-Json -Depth 20 -Compress
            Check ($left -ceq $right) "$problemId`: applied property not submitted $($componentStep.component.nodeId).$key"
        }
    }
    foreach ($connectionStep in $connections) {
        $expected = $connectionStep.connection
        $actual = @($request.connections | Where-Object id -eq $expected.edgeId)[0]
        Check ($actual.source -eq $expected.sourceNodeId -and $actual.target -eq $expected.targetNodeId) "$problemId`: connection endpoints differ $($expected.edgeId)"
        Check ($actual.type -eq $expected.connectionType -and $actual.description -ceq $expected.description) "$problemId`: connection semantics not submitted $($expected.edgeId)"
    }
    $appliedIds = @(@($attempt.nodes) + @($attempt.edges) | ForEach-Object { $_.data._guidedAppliedSteps } | Sort-Object -Unique)
    foreach ($action in $actions) { Check ($appliedIds -contains $action.id) "$problemId`: saved applied action missing $($action.id)" }
    $core = @(@($request.problem.requirementSpec.functional) + @($request.problem.requirementSpec.nonFunctional) | Where-Object scope -eq 'core')
    foreach ($requirement in @($core | Where-Object { $null -ne $review })) {
        $coverage = @($review.requirement_coverage | Where-Object requirement_id -eq $requirement.id)
        Check ($coverage.Count -eq 1 -and $coverage[0].status -eq 'supported') "$problemId`: core requirement not supported $($requirement.id)"
    }
    $results.Add([pscustomobject]@{problemId=$problemId;score=$review.overall_score;verdict=$review.verdict;components=$request.components.Count;connections=$request.connections.Count;appliedActions=$appliedIds.Count;coreRequirements=$core.Count})
}

$document = @($session.attempts | Where-Object problemId -eq '6901ef1b9420d83630aca871')[0]
$fallback = @($session.assessmentOutputs | Where-Object source -eq 'rule_based')[0]
Check ($fallback.score_available -eq $false -and $fallback.verdict -eq 'unavailable') 'Outage: fallback misrepresented as scored review'
Check ($document.lastAssessment.source -eq 'ai' -and $document.lastAssessment.score -eq 97) 'Outage: last successful AI review lost'
Check ($document.lastAssessmentCheck.scoreAvailable -eq $false) 'Outage: latest structure check lost'
Check ($document.assessmentCount -eq 1) 'Outage: AI count changed by unscored check'
$unscoredHistory = @($document.assessmentHistory | Where-Object scoreAvailable -eq $false)
Check ($unscoredHistory.Count -eq 1 -and $null -eq $unscoredHistory[0].score) 'Outage: history has fabricated score'

$results | Format-Table -AutoSize
if ($failures.Count) {
    $failures | ForEach-Object { Write-Output "FAIL: $_" }
    throw "$($failures.Count) captured-evidence assertions failed"
}
Write-Output 'PASS: all five browser-built submissions, saved applied evidence, typed scope, AI scores, and outage history'
Write-Output 'This does not override separately observed autosave/mobile failures or prove deployed reliability.'
